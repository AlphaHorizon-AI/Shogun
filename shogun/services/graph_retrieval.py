"""Authorized graph expansion for Phase 3 retrieval."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.memory_graph import MemoryGraphEdge, MemoryGraphNode
from shogun.db.models.memory_record import MemoryRecord
from shogun.engine.memory_salience import compute_decayed_relevance, compute_recency_boost
from shogun.schemas.memory import MemoryScopeEnvelope
from shogun.services.memory_scope import authorization_predicates


@dataclass
class GraphExpansionResult:
    results: list[dict[str, Any]] = field(default_factory=list)
    excluded: list[dict[str, Any]] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


class GraphRetrievalService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _shared_scope_match(record: MemoryRecord, scope: MemoryScopeEnvelope) -> bool:
        if record.scope_status != "classified":
            return False
        shared_fields = (
            "team_id",
            "workspace_id",
            "project_id",
            "workflow_id",
            "conversation_id",
            "topic_id",
        )
        return any(
            getattr(scope, field) is not None
            and getattr(record, field) == getattr(scope, field)
            for field in shared_fields
        )

    @staticmethod
    def _scope_score(record: MemoryRecord, scope: MemoryScopeEnvelope) -> float:
        fields = ("team_id", "workspace_id", "project_id", "workflow_id", "conversation_id", "topic_id")
        requested = [field for field in fields if getattr(scope, field) is not None]
        if not requested:
            return 0.5
        matches = sum(getattr(record, field) == getattr(scope, field) for field in requested)
        return matches / len(requested)

    async def expand(
        self,
        *,
        seed_results: list[dict[str, Any]],
        scope: MemoryScopeEnvelope,
        agent_id: uuid.UUID | None,
        limit: int | None = None,
    ) -> GraphExpansionResult:
        seed_memory_ids = {uuid.UUID(str(item["memory_id"])) for item in seed_results}
        if not seed_memory_ids:
            return GraphExpansionResult(diagnostics={"seed_count": 0, "reason": "no_seed_memories"})

        seed_nodes = list(
            (
                await self.session.scalars(
                    select(MemoryGraphNode).where(MemoryGraphNode.source_memory_id.in_(seed_memory_ids))
                )
            ).all()
        )
        if not seed_nodes:
            return GraphExpansionResult(
                diagnostics={
                    "seed_count": len(seed_memory_ids),
                    "linked_seed_count": 0,
                    "reason": "seeds_not_backfilled",
                }
            )

        allowed_relationships = {
            item.strip()
            for item in settings.memory_graph_allowed_relationships.split(",")
            if item.strip()
        }
        max_depth = min(max(settings.memory_graph_max_depth, 1), 2)
        max_results = limit or settings.memory_graph_max_expansion_results
        node_scores = {node.id: 1.0 for node in seed_nodes}
        node_depths = {node.id: 0 for node in seed_nodes}
        node_paths: dict[uuid.UUID, list[str]] = {node.id: [] for node in seed_nodes}
        visited = set(node_scores)
        frontier = set(visited)

        for depth in range(1, max_depth + 1):
            if not frontier:
                break
            edges = list(
                (
                    await self.session.scalars(
                        select(MemoryGraphEdge).where(
                            MemoryGraphEdge.status == "active",
                            MemoryGraphEdge.relationship_type.in_(allowed_relationships),
                            MemoryGraphEdge.weight >= settings.memory_graph_min_edge_weight,
                            or_(
                                MemoryGraphEdge.from_node_id.in_(frontier),
                                MemoryGraphEdge.to_node_id.in_(frontier),
                            ),
                        )
                    )
                ).all()
            )
            next_frontier: set[uuid.UUID] = set()
            for edge in edges:
                endpoints = ((edge.from_node_id, edge.to_node_id), (edge.to_node_id, edge.from_node_id))
                for current_id, adjacent_id in endpoints:
                    if current_id not in frontier:
                        continue
                    score = node_scores[current_id] * edge.weight * edge.confidence * (0.85 ** (depth - 1))
                    if score <= node_scores.get(adjacent_id, -1.0):
                        continue
                    node_scores[adjacent_id] = score
                    node_depths[adjacent_id] = depth
                    node_paths[adjacent_id] = [*node_paths[current_id], edge.relationship_type]
                    if adjacent_id not in visited:
                        next_frontier.add(adjacent_id)
            visited.update(next_frontier)
            frontier = next_frontier

        candidate_node_ids = set(node_scores) - {node.id for node in seed_nodes}
        if not candidate_node_ids:
            return GraphExpansionResult(
                diagnostics={
                    "seed_count": len(seed_memory_ids),
                    "linked_seed_count": len(seed_nodes),
                    "visited_node_count": len(visited),
                    "candidate_memory_count": 0,
                }
            )
        candidate_nodes = list(
            (
                await self.session.scalars(
                    select(MemoryGraphNode).where(MemoryGraphNode.id.in_(candidate_node_ids))
                )
            ).all()
        )
        memory_nodes = [node for node in candidate_nodes if node.source_memory_id]
        candidate_memory_ids = {node.source_memory_id for node in memory_nodes} - seed_memory_ids
        if not candidate_memory_ids:
            return GraphExpansionResult(
                diagnostics={
                    "seed_count": len(seed_memory_ids),
                    "linked_seed_count": len(seed_nodes),
                    "visited_node_count": len(visited),
                    "candidate_memory_count": 0,
                }
            )

        allow_shared = settings.memory_graph_shared_agent_reads_enabled
        predicates = authorization_predicates(
            scope=scope,
            agent_id=None if allow_shared else agent_id,
        )
        records = list(
            (
                await self.session.scalars(
                    select(MemoryRecord).where(MemoryRecord.id.in_(candidate_memory_ids), *predicates)
                )
            ).all()
        )
        node_by_memory = {node.source_memory_id: node for node in memory_nodes}
        accepted: list[dict[str, Any]] = []
        authorized_ids = {record.id for record in records}
        excluded: list[dict[str, Any]] = [
            {"memory_id": str(memory_id), "reason": "scope_or_sensitivity_not_authorized"}
            for memory_id in candidate_memory_ids - authorized_ids
        ]
        for record in records:
            if agent_id and record.agent_id != agent_id:
                if not allow_shared or not self._shared_scope_match(record, scope):
                    excluded.append({"memory_id": str(record.id), "reason": "cross_agent_share_not_authorized"})
                    continue
            node = node_by_memory[record.id]
            relevance = compute_decayed_relevance(
                record.relevance_score,
                record.decay_class,
                record.last_confirmed_at or record.created_at,
                record.is_pinned,
            )
            recency = compute_recency_boost(record.updated_at)
            graph_relevance = min(max(node_scores[node.id], 0.0), 1.0)
            scope_match = self._scope_score(record, scope)
            final = min(
                1.0,
                (0.30 * graph_relevance)
                + (0.20 * relevance)
                + (0.15 * record.importance_score)
                + (0.10 * record.confidence_score)
                + (0.10 * recency)
                + (0.15 * scope_match),
            )
            accepted.append(
                {
                    "memory_id": str(record.id),
                    "memory_type": record.memory_type,
                    "title": record.title,
                    "content": record.content,
                    "scores": {
                        "semantic_similarity": 0.0,
                        "graph_relevance": graph_relevance,
                        "scope_match": scope_match,
                        "relevance_score": relevance,
                        "importance_score": record.importance_score,
                        "confidence_score": record.confidence_score,
                        "recency_boost": recency,
                        "final": final,
                    },
                    "decay_class": record.decay_class,
                    "access_count": record.access_count,
                    "successful_use_count": record.successful_use_count,
                    "is_pinned": record.is_pinned,
                    "last_confirmed_at": record.last_confirmed_at,
                    "retrieval_stage": "memory_graph_expansion",
                    "retrieval_source": "memory_graph",
                    "graph_status": node.status,
                    "graph_depth": node_depths[node.id],
                    "graph_path": node_paths[node.id],
                    "source_agent_id": str(record.agent_id),
                }
            )
        accepted.sort(key=lambda item: item["scores"]["final"], reverse=True)
        return GraphExpansionResult(
            results=accepted[:max_results],
            excluded=excluded,
            diagnostics={
                "seed_count": len(seed_memory_ids),
                "linked_seed_count": len(seed_nodes),
                "visited_node_count": len(visited),
                "candidate_memory_count": len(candidate_memory_ids),
                "authorized_candidate_count": len(accepted),
                "returned_count": min(len(accepted), max_results),
                "max_depth": max_depth,
            },
        )
