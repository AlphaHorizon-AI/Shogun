"""Kiroku MemoryGraph orchestration and safe legacy-memory backfill."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.memory_graph import MemoryGraphConflict, MemoryGraphEdge, MemoryGraphNode
from shogun.db.models.memory_record import MemoryRecord
from shogun.engine.vector_store import get_vector_store
from shogun.schemas.memory_graph import (
    MemoryGraphBackfillResponse,
    MemoryGraphEdgeCreate,
    MemoryGraphNodeCreate,
    MemoryGraphNodeUpdate,
)
from shogun.services.memory_graph_repository import MemoryGraphRepository

logger = logging.getLogger(__name__)

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,59}$")


def _normalized_identifier(value: str, label: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    if not _IDENTIFIER.fullmatch(normalized):
        raise ValueError(f"Invalid {label}: use lowercase letters, numbers, and underscores")
    return normalized


class MemoryGraphService:
    """Maintains graph structure without changing the authoritative memory record."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = MemoryGraphRepository(session)

    @staticmethod
    def memory_key(memory_id: uuid.UUID) -> str:
        return f"memory:{memory_id}"

    @staticmethod
    def scope_key(tenant_id: str, node_type: str, value: str) -> str:
        return f"scope:{tenant_id}:{node_type.lower()}:{value}"

    async def create_node(self, body: MemoryGraphNodeCreate) -> MemoryGraphNode:
        node_type = _normalized_identifier(body.node_type, "node_type")
        scope = body.scope
        if body.source_memory_id:
            memory = await self.session.get(MemoryRecord, body.source_memory_id)
            if memory is None:
                raise LookupError("Source memory not found")
            node, _counts = await self.ensure_memory_node(memory)
            return node
        canonical_key = body.canonical_key or f"manual:{scope.tenant_id}:{node_type}:{uuid.uuid4()}"
        if await self.repository.node_by_key(canonical_key):
            raise ValueError("A graph node with that canonical_key already exists")
        node = MemoryGraphNode(
            canonical_key=canonical_key,
            node_type=node_type,
            name=body.name,
            display_name=body.display_name,
            payload_json=body.payload_json,
            scope_json=scope.model_dump(mode="json", exclude_none=True),
            tenant_id=scope.tenant_id,
            user_id=scope.user_id,
            team_id=scope.team_id,
            workspace_id=scope.workspace_id,
            project_id=scope.project_id,
            agent_id=scope.agent_id,
            topic_id=scope.topic_id,
            sensitivity=body.sensitivity,
            source_memory_id=body.source_memory_id,
            qdrant_point_id=body.qdrant_point_id,
        )
        self.session.add(node)
        await self.session.flush()
        await self.session.refresh(node)
        return node

    async def update_node(
        self, node_id: uuid.UUID, body: MemoryGraphNodeUpdate
    ) -> MemoryGraphNode | None:
        node = await self.repository.node(node_id)
        if node is None:
            return None
        for key, value in body.model_dump(exclude_unset=True).items():
            setattr(node, key, value)
        await self.session.flush()
        await self.session.refresh(node)
        return node

    async def deprecate_node(self, node_id: uuid.UUID) -> bool:
        node = await self.repository.node(node_id)
        if node is None:
            return False
        node.status = "deprecated"
        for edge in await self.repository.edges(node_id=node_id, limit=5000):
            edge.status = "deprecated"
        await self.session.flush()
        return True

    async def create_edge(self, body: MemoryGraphEdgeCreate) -> MemoryGraphEdge:
        relationship = _normalized_identifier(body.relationship_type, "relationship_type")
        source = await self.repository.node(body.from_node_id)
        target = await self.repository.node(body.to_node_id)
        if source is None or target is None:
            raise LookupError("Both graph nodes must exist")
        if source.tenant_id != target.tenant_id:
            raise ValueError("Cross-tenant graph edges are not allowed")
        existing = await self.repository.edge_by_relation(source.id, target.id, relationship)
        if existing:
            existing.weight = body.weight
            existing.confidence = body.confidence
            existing.payload_json = body.payload_json
            existing.source_memory_id = body.source_memory_id
            existing.status = "active"
            await self.session.flush()
            return existing
        edge = MemoryGraphEdge(
            from_node_id=source.id,
            to_node_id=target.id,
            relationship_type=relationship,
            weight=body.weight,
            confidence=body.confidence,
            source_memory_id=body.source_memory_id,
            payload_json=body.payload_json,
        )
        self.session.add(edge)
        await self.session.flush()
        await self.session.refresh(edge)
        return edge

    async def _ensure_scope_node(
        self,
        *,
        memory: MemoryRecord,
        node_type: str,
        value: str,
        name: str,
    ) -> tuple[MemoryGraphNode, bool]:
        key = self.scope_key(memory.tenant_id, node_type, value)
        existing = await self.repository.node_by_key(key)
        if existing:
            sensitivity_order = {"public": 0, "internal": 1, "confidential": 2, "restricted": 3}
            if sensitivity_order.get(memory.sensitivity, 1) > sensitivity_order.get(existing.sensitivity, 1):
                existing.sensitivity = memory.sensitivity
            return existing, False
        scope = self._entity_scope(memory, node_type)
        node = MemoryGraphNode(
            id=uuid.uuid5(uuid.NAMESPACE_URL, key),
            canonical_key=key,
            node_type=node_type,
            name=name,
            display_name=name,
            payload_json={"external_id": value},
            scope_json=scope,
            tenant_id=memory.tenant_id,
            user_id=scope.get("user_id"),
            team_id=scope.get("team_id"),
            workspace_id=scope.get("workspace_id"),
            project_id=scope.get("project_id"),
            agent_id=uuid.UUID(scope["agent_id"]) if scope.get("agent_id") else None,
            topic_id=scope.get("topic_id"),
            sensitivity=memory.sensitivity,
        )
        self.session.add(node)
        await self.session.flush()
        return node, True

    @staticmethod
    def _memory_scope(memory: MemoryRecord) -> dict[str, Any]:
        fields = (
            "tenant_id",
            "user_id",
            "team_id",
            "workspace_id",
            "project_id",
            "workflow_id",
            "conversation_provider",
            "conversation_id",
            "topic_id",
            "sensitivity",
            "scope_status",
            "policy_version",
        )
        return {field: getattr(memory, field, None) for field in fields if getattr(memory, field, None) is not None}

    @staticmethod
    def _entity_scope(memory: MemoryRecord, node_type: str) -> dict[str, Any]:
        """Keep shared entity nodes from inheriting an unrelated narrower scope."""
        scope: dict[str, Any] = {"tenant_id": memory.tenant_id}
        fields_by_type = {
            "agent": ("agent_id",),
            "user": ("user_id",),
            "team": ("team_id",),
            "workspace": ("workspace_id",),
            "project": ("workspace_id", "project_id"),
            "workflow": ("workspace_id", "project_id", "workflow_id"),
            "conversation": (
                "user_id",
                "team_id",
                "conversation_provider",
                "conversation_id",
            ),
            "topic": (
                "user_id",
                "team_id",
                "conversation_provider",
                "conversation_id",
                "topic_id",
            ),
        }
        for field in fields_by_type.get(node_type, ()):
            value = getattr(memory, field, None)
            if value is not None:
                scope[field] = str(value) if isinstance(value, uuid.UUID) else value
        return scope

    async def ensure_memory_node(
        self, memory: MemoryRecord, *, link_scopes: bool = True, update_vector: bool = True
    ) -> tuple[MemoryGraphNode, dict[str, int]]:
        key = self.memory_key(memory.id)
        node = await self.repository.node_by_key(key)
        created = node is None
        payload = {
            "memory_type": memory.memory_type,
            "title": memory.title,
            "summary": memory.summary,
            "content_hash": memory.content_hash,
            "tags": memory.tags or [],
            "scope_status": memory.scope_status,
        }
        if node is None:
            node = MemoryGraphNode(
                id=memory.id,
                canonical_key=key,
                node_type="memory_chunk",
                name=memory.title,
                display_name=memory.title,
                payload_json=payload,
                scope_json=self._memory_scope(memory),
                tenant_id=memory.tenant_id,
                user_id=memory.user_id,
                team_id=memory.team_id,
                workspace_id=memory.workspace_id,
                project_id=memory.project_id,
                agent_id=memory.agent_id,
                topic_id=memory.topic_id,
                sensitivity=memory.sensitivity,
                status="deprecated" if memory.is_archived else "active",
                source_memory_id=memory.id,
                qdrant_point_id=memory.qdrant_point_id,
            )
            self.session.add(node)
            await self.session.flush()
        else:
            node.name = memory.title
            node.display_name = memory.title
            node.payload_json = payload
            node.scope_json = self._memory_scope(memory)
            node.sensitivity = memory.sensitivity
            node.qdrant_point_id = memory.qdrant_point_id
            if memory.is_archived:
                node.status = "deprecated"

        counts = {"memory_nodes_created": int(created), "scope_nodes_created": 0, "edges_created": 0}
        if link_scopes:
            links: list[tuple[str, str, str, str]] = [
                ("agent", str(memory.agent_id), f"Agent {memory.agent_id}", "created_by")
            ]
            for node_type, value, label, relationship in (
                ("user", memory.user_id, "User", "visible_to"),
                ("team", memory.team_id, "Team", "visible_to"),
                ("workspace", memory.workspace_id, "Workspace", "belongs_to"),
                ("project", memory.project_id, "Project", "belongs_to"),
                ("workflow", memory.workflow_id, "Workflow", "part_of_workflow"),
                ("conversation", memory.conversation_id, "Conversation", "belongs_to"),
                ("topic", memory.topic_id, "Topic", "stored_in_topic"),
            ):
                if value:
                    links.append((node_type, str(value), f"{label} {value}", relationship))
            for node_type, value, label, relationship in links:
                scope_node, scope_created = await self._ensure_scope_node(
                    memory=memory, node_type=node_type, value=value, name=label
                )
                counts["scope_nodes_created"] += int(scope_created)
                edge_created = (
                    await self.repository.edge_by_relation(node.id, scope_node.id, relationship)
                ) is None
                await self.create_edge(
                    MemoryGraphEdgeCreate(
                        from_node_id=node.id,
                        to_node_id=scope_node.id,
                        relationship_type=relationship,
                        source_memory_id=memory.id,
                    )
                )
                counts["edges_created"] += int(edge_created)

        if update_vector and memory.qdrant_point_id:
            try:
                get_vector_store().set_payload(
                    memory_id=str(memory.id),
                    payload={"graph_node_id": str(node.id), "graph_status": node.status},
                )
            except Exception as exc:
                logger.warning("Could not link Qdrant memory %s to MemoryGraph: %s", memory.id, exc)
        await self.session.flush()
        return node, counts

    async def backfill(
        self, *, limit: int = 250, after_memory_id: uuid.UUID | None = None, include_archived: bool = False
    ) -> MemoryGraphBackfillResponse:
        query = select(MemoryRecord)
        if not include_archived:
            query = query.where(MemoryRecord.is_archived.is_(False))
        if after_memory_id:
            query = query.where(MemoryRecord.id > after_memory_id)
        result = await self.session.execute(query.order_by(MemoryRecord.id).limit(limit + 1))
        records = list(result.scalars().all())
        complete = len(records) <= limit
        batch = records[:limit]
        totals = {"memory_nodes_created": 0, "scope_nodes_created": 0, "edges_created": 0}
        for memory in batch:
            _node, counts = await self.ensure_memory_node(memory)
            for key in totals:
                totals[key] += counts[key]
        return MemoryGraphBackfillResponse(
            scanned=len(batch),
            **totals,
            next_after_memory_id=batch[-1].id if batch and not complete else None,
            complete=complete,
        )

    async def create_conflict(
        self, memory_id_a: uuid.UUID, memory_id_b: uuid.UUID, conflict_type: str = "contradiction"
    ) -> MemoryGraphConflict:
        conflict_type = _normalized_identifier(conflict_type, "conflict_type")
        first = await self.session.get(MemoryRecord, memory_id_a)
        second = await self.session.get(MemoryRecord, memory_id_b)
        if first is None or second is None:
            raise LookupError("Both memories must exist")
        if first.tenant_id != second.tenant_id:
            raise ValueError("Cross-tenant conflicts are not allowed")
        first_node, _ = await self.ensure_memory_node(first, update_vector=False)
        second_node, _ = await self.ensure_memory_node(second, update_vector=False)
        first_node.status = "conflicting"
        second_node.status = "conflicting"
        await self.create_edge(
            MemoryGraphEdgeCreate(
                from_node_id=first_node.id,
                to_node_id=second_node.id,
                relationship_type="conflicts_with",
                source_memory_id=second.id,
            )
        )
        conflict = MemoryGraphConflict(
            memory_id_a=first.id,
            memory_id_b=second.id,
            conflict_type=conflict_type,
        )
        self.session.add(conflict)
        await self.session.flush()
        await self.session.refresh(conflict)
        return conflict

    async def resolve_conflict(
        self,
        conflict_id: uuid.UUID,
        *,
        resolution_status: str,
        resolved_by: str,
        resolution_note: str,
        superseding_memory_id: uuid.UUID | None = None,
    ) -> MemoryGraphConflict | None:
        conflict = await self.repository.conflict(conflict_id)
        if conflict is None:
            return None
        memory_ids = {conflict.memory_id_a, conflict.memory_id_b}
        if superseding_memory_id and superseding_memory_id not in memory_ids:
            raise ValueError("superseding_memory_id must be one of the conflicting memories")
        nodes: dict[uuid.UUID, MemoryGraphNode] = {}
        for memory_id in memory_ids:
            memory = await self.session.get(MemoryRecord, memory_id)
            if memory:
                nodes[memory_id] = (await self.ensure_memory_node(memory, update_vector=False))[0]
        if superseding_memory_id:
            old_memory_id = next(memory_id for memory_id in memory_ids if memory_id != superseding_memory_id)
            newer = nodes[superseding_memory_id]
            older = nodes[old_memory_id]
            newer.status = "active"
            older.status = "superseded"
            await self.create_edge(
                MemoryGraphEdgeCreate(
                    from_node_id=newer.id,
                    to_node_id=older.id,
                    relationship_type="supersedes",
                    source_memory_id=superseding_memory_id,
                )
            )
        elif resolution_status in {"resolved", "dismissed"}:
            for node in nodes.values():
                node.status = "active"
        conflict.resolution_status = resolution_status
        conflict.resolved_by = resolved_by
        conflict.resolution_note = resolution_note
        conflict.resolved_at = datetime.now(timezone.utc)
        await self.session.flush()
        await self.session.refresh(conflict)
        return conflict

    async def neighborhood(
        self, node_id: uuid.UUID, *, depth: int = 1, limit: int = 250
    ) -> tuple[list[MemoryGraphNode], list[MemoryGraphEdge]]:
        root = await self.repository.node(node_id)
        if root is None:
            raise LookupError("Graph node not found")
        nodes = {root.id: root}
        edges: dict[uuid.UUID, MemoryGraphEdge] = {}
        frontier = {root.id}
        for _ in range(depth):
            next_frontier: set[uuid.UUID] = set()
            for current_id in frontier:
                for edge in await self.repository.edges(node_id=current_id, limit=limit):
                    edges[edge.id] = edge
                    adjacent_id = edge.to_node_id if edge.from_node_id == current_id else edge.from_node_id
                    adjacent = await self.repository.node(adjacent_id)
                    if adjacent and adjacent.tenant_id == root.tenant_id and adjacent.id not in nodes:
                        nodes[adjacent.id] = adjacent
                        next_frontier.add(adjacent.id)
                    if len(nodes) >= limit:
                        return list(nodes.values()), list(edges.values())
            frontier = next_frontier
            if not frontier:
                break
        return list(nodes.values()), list(edges.values())
