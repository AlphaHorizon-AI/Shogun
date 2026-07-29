"""Memory service — metadata CRUD + salience + vector search.

Wraps the memory record ORM model and integrates:
  - SQLite for metadata, salience scores, and lifecycle
  - Qdrant for vector similarity search
  - Salience engine for decay, reinforcement, and reranking
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.memory_record import MemoryRecord
from shogun.engine.memory_salience import (
    ScoredMemory,
    compute_decayed_relevance,
    compute_recency_boost,
    compute_reinforced_relevance,
    rerank_candidates,
)
from shogun.engine.vector_store import get_vector_store
from shogun.schemas.memory import MemoryScopeEnvelope
from shogun.services.base_service import BaseService
from shogun.services.memory_governance import validate_decay_type
from shogun.services.memory_scope import (
    authorization_predicates,
    authorized_memory_ids,
    coerce_scope,
    resolve_active_memory_scope,
)

logger = logging.getLogger(__name__)


class MemoryService(BaseService[MemoryRecord]):
    """Service for memory record CRUD, vector search, and salience operations.

    Every memory is dual-written:
      1. SQLite — full metadata, salience scores, lifecycle state
      2. Qdrant — vector embedding + filterable payload

    Search flow:
      Query → embed → Qdrant (top-N candidates) → SQLite (full metadata)
      → salience reranker → scored results
    """

    def __init__(self, session: AsyncSession):
        super().__init__(MemoryRecord, session)

    # ── Create with dual-write ──────────────────────────────────

    async def create_memory(
        self,
        *,
        memory_type: str,
        agent_id: uuid.UUID,
        title: str,
        content: str,
        summary: str | None = None,
        relevance_score: float = 0.7,
        importance_score: float = 0.5,
        confidence_score: float = 0.5,
        decay_class: str = "medium",
        is_pinned: bool = False,
        tags: list[str] | None = None,
        scope: MemoryScopeEnvelope | dict[str, Any] | None = None,
        sensitivity: str = "internal",
        **kwargs: Any,
    ) -> MemoryRecord:
        """Create a memory with dual-write to SQLite + Qdrant."""
        validated_decay = validate_decay_type(decay_class)
        decay_class = validated_decay or "medium"
        memory_scope = resolve_active_memory_scope(scope)
        scope_data = memory_scope.model_dump(exclude={"sensitivity_ceiling", "include_legacy_agent_memory"})
        classified = any(
            scope_data.get(field)
            for field in (
                "user_id",
                "team_id",
                "workspace_id",
                "project_id",
                "workflow_id",
                "conversation_id",
                "topic_id",
            )
        )
        # 1. SQLite insert
        record = await self.create(
            memory_type=memory_type,
            agent_id=agent_id,
            title=title,
            content=content,
            summary=summary,
            relevance_score=relevance_score,
            importance_score=importance_score,
            confidence_score=confidence_score,
            decay_class=decay_class,
            is_pinned=is_pinned,
            tags=tags or [],
            sensitivity=sensitivity,
            scope_status="classified" if classified else "agent_private",
            **scope_data,
            **kwargs,
        )

        # 2. Qdrant upsert (async-safe — qdrant-client handles this)
        try:
            store = get_vector_store()
            # Combine title + content for richer embedding
            embed_text = f"{title}\n\n{content}"
            if summary:
                embed_text = f"{title}\n\n{summary}\n\n{content}"

            store.upsert(
                memory_id=str(record.id),
                text=embed_text,
                payload={
                    "memory_type": memory_type,
                    "agent_id": str(agent_id),
                    "title": title,
                    "importance_score": importance_score,
                    "decay_class": decay_class,
                    "is_pinned": is_pinned,
                    "tags": tags or [],
                    "sensitivity": sensitivity,
                    "scope_status": record.scope_status,
                    "tenant_id": record.tenant_id,
                    "user_id": record.user_id,
                    "team_id": record.team_id,
                    "workspace_id": record.workspace_id,
                    "project_id": record.project_id,
                    "workflow_id": record.workflow_id,
                    "conversation_provider": record.conversation_provider,
                    "conversation_id": record.conversation_id,
                    "topic_id": record.topic_id,
                    "policy_version": record.policy_version,
                    "graph_node_id": str(record.id),
                    "graph_status": "active" if settings.memory_graph_write_mode == "dual" else "pending",
                },
            )
            # Store the Qdrant point ID on the record
            record.qdrant_point_id = str(record.id)
            await self.session.flush()
        except Exception as e:
            logger.warning("Failed to upsert memory %s to Qdrant: %s", record.id, e)

        if settings.memory_graph_write_mode == "dual":
            try:
                # A savepoint keeps memory creation healthy if the optional
                # graph layer is temporarily unavailable.
                async with self.session.begin_nested():
                    from shogun.services.memory_graph_service import MemoryGraphService

                    await MemoryGraphService(self.session).ensure_memory_node(record)
            except Exception as e:
                logger.warning("Failed to link memory %s into MemoryGraph: %s", record.id, e)

        return record

    # ── Hybrid search ───────────────────────────────────────────

    async def search(
        self,
        query: str,
        *,
        agent_id: uuid.UUID | None = None,
        memory_types: list[str] | None = None,
        min_importance: float | None = None,
        pinned_only: bool = False,
        decay_class: str | None = None,
        limit: int = 20,
        weight_overrides: dict[str, float] | None = None,
        scope: MemoryScopeEnvelope | dict[str, Any] | None = None,
        required_scope_field: str | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid semantic search: Qdrant vector retrieval + salience reranking.

        Returns scored, ranked memory results with full metadata.
        """
        decay_class = validate_decay_type(decay_class)
        memory_scope = coerce_scope(scope)
        store = get_vector_store()

        allowed_ids = None
        if memory_scope is not None:
            allowed_ids = await authorized_memory_ids(
                self.session,
                scope=memory_scope,
                agent_id=agent_id,
                required_scope_field=required_scope_field,
                memory_types=memory_types,
                min_importance=min_importance,
                pinned_only=pinned_only,
            )
            if not allowed_ids:
                return []

        # 1. Vector search in Qdrant (runs in thread pool to avoid blocking event loop)
        qdrant_hits = await asyncio.to_thread(
            store.search,
            query_text=query,
            memory_types=memory_types,
            agent_id=str(agent_id) if agent_id else None,
            min_importance=min_importance,
            pinned_only=pinned_only,
            allowed_memory_ids=allowed_ids,
            limit=limit * 2,  # over-fetch for better reranking
        )

        # 2. Fetch full metadata from SQLite. Sticky memories for an explicit
        # agent scope remain eligible even when semantic retrieval misses them.
        hit_ids = [uuid.UUID(h["memory_id"]) for h in qdrant_hits]
        similarity_map = {h["memory_id"]: h["score"] for h in qdrant_hits}
        records: dict[str, MemoryRecord] = {}
        if hit_ids:
            predicates = [MemoryRecord.id.in_(hit_ids), MemoryRecord.is_archived.is_(False)]
            if agent_id is not None:
                predicates.append(MemoryRecord.agent_id == agent_id)
            if memory_scope is not None:
                predicates.extend(
                    authorization_predicates(
                        scope=memory_scope,
                        agent_id=agent_id,
                        required_scope_field=required_scope_field,
                    )
                )
            result = await self.session.execute(select(MemoryRecord).where(*predicates))
            records = {str(r.id): r for r in result.scalars().all()}

        sticky_considered = 0
        sticky_skipped_token_budget = 0
        if agent_id and not pinned_only and decay_class in (None, "sticky"):
            sticky_query = select(MemoryRecord).where(
                MemoryRecord.agent_id == agent_id,
                MemoryRecord.decay_class == "sticky",
                MemoryRecord.is_archived.is_(False),
            )
            if memory_scope is not None:
                sticky_query = sticky_query.where(
                    *authorization_predicates(
                        scope=memory_scope,
                        agent_id=agent_id,
                        required_scope_field=required_scope_field,
                    )
                )
            if memory_types:
                sticky_query = sticky_query.where(MemoryRecord.memory_type.in_(memory_types))
            if min_importance is not None:
                sticky_query = sticky_query.where(MemoryRecord.importance_score >= min_importance)
            sticky_query = sticky_query.order_by(
                MemoryRecord.importance_score.desc(),
                MemoryRecord.created_at.desc(),
            ).limit(settings.memory_max_sticky_memories_in_context)
            sticky_result = await self.session.execute(sticky_query)
            sticky_records = list(sticky_result.scalars().all())
            sticky_considered = len(sticky_records)
            sticky_token_budget = settings.memory_max_sticky_context_tokens
            for record in sticky_records:
                estimated_tokens = max((len(record.title) + len(record.content) + 3) // 4, 1)
                if estimated_tokens > sticky_token_budget:
                    sticky_skipped_token_budget += 1
                    continue
                sticky_token_budget -= estimated_tokens
                records[str(record.id)] = record
                similarity_map.setdefault(str(record.id), 0.0)

        if decay_class:
            records = {
                memory_id: record
                for memory_id, record in records.items()
                if record.decay_class == decay_class
            }
        if not records and not sticky_considered:
            return []

        # 3. Build scored candidates
        now = datetime.now(timezone.utc)
        candidates: list[ScoredMemory] = []

        for mid, record in records.items():

            # Compute live scores
            effective_relevance = compute_decayed_relevance(
                current_relevance=record.relevance_score,
                decay_class=record.decay_class,
                last_confirmed_at=record.last_confirmed_at,
                is_pinned=record.is_pinned,
                now=now,
            )
            recency = compute_recency_boost(
                last_accessed_at=record.last_accessed_at,
                now=now,
            )

            candidates.append(
                ScoredMemory(
                    memory_id=mid,
                    memory_type=record.memory_type,
                    title=record.title,
                    content=record.content,
                    semantic_similarity=similarity_map.get(mid, 0.0),
                    relevance_score=effective_relevance,
                    importance_score=record.importance_score,
                    confidence_score=record.confidence_score,
                    recency_boost=recency,
                    decay_class=record.decay_class,
                    access_count=record.access_count,
                    successful_use_count=record.successful_use_count,
                    is_pinned=record.is_pinned,
                    last_confirmed_at=record.last_confirmed_at,
                )
            )

        # 4. Rerank using salience engine
        ranked = rerank_candidates(candidates, weight_overrides=weight_overrides)
        ranked.sort(key=lambda candidate: candidate.decay_class != "sticky")

        # 5. Return top-N with full score breakdown + all fields the frontend needs
        results_out = []
        for c in ranked[:limit]:
            record = records.get(c.memory_id)
            results_out.append({
                "id": c.memory_id,
                "memory_id": c.memory_id,
                "memory_type": c.memory_type,
                "agent_id": str(record.agent_id) if record else None,
                "title": c.title,
                "content": c.content,
                "summary": record.summary if record else None,
                "relevance_score": round(c.relevance_score, 4),
                "importance_score": round(c.importance_score, 4),
                "confidence_score": round(c.confidence_score, 4),
                "scores": {
                    "semantic_similarity": round(c.semantic_similarity, 4),
                    "relevance_score": round(c.relevance_score, 4),
                    "importance_score": round(c.importance_score, 4),
                    "confidence_score": round(c.confidence_score, 4),
                    "recency_boost": round(c.recency_boost, 4),
                    "final": round(c.final_score, 4),
                },
                "decay_class": c.decay_class,
                "access_count": c.access_count,
                "successful_use_count": c.successful_use_count,
                "recall_count": record.recall_count if record else 0,
                "is_pinned": c.is_pinned,
                "is_archived": False,
                "created_at": record.created_at.isoformat() if record and record.created_at else None,
                "updated_at": record.updated_at.isoformat() if record and record.updated_at else None,
                "last_accessed_at": record.last_accessed_at.isoformat() if record and record.last_accessed_at else None,
                "last_confirmed_at": c.last_confirmed_at.isoformat() if c.last_confirmed_at else None,
                "scope": {
                    "tenant_id": record.tenant_id if record else None,
                    "user_id": record.user_id if record else None,
                    "team_id": record.team_id if record else None,
                    "workspace_id": record.workspace_id if record else None,
                    "project_id": record.project_id if record else None,
                    "workflow_id": record.workflow_id if record else None,
                    "conversation_provider": record.conversation_provider if record else None,
                    "conversation_id": record.conversation_id if record else None,
                    "topic_id": record.topic_id if record else None,
                },
                "sensitivity": record.sensitivity if record else "internal",
                "scope_status": record.scope_status if record else "agent_private",
            })
        if sticky_considered:
            sticky_injected = sum(item["decay_class"] == "sticky" for item in results_out)
            logger.info(
                "Sticky memories considered=%d injected=%d token_skipped=%d cap=%d agent_id=%s",
                sticky_considered,
                sticky_injected,
                sticky_skipped_token_budget,
                settings.memory_max_sticky_memories_in_context,
                agent_id,
            )
            from shogun.services.event_logger import EventLogger

            await EventLogger.emit(
                category="memory",
                event_type="memory.retrieval.sticky_injected",
                action="Injected governed sticky memories into retrieval results",
                agent_id=str(agent_id),
                detail={
                    "sticky_considered": sticky_considered,
                    "sticky_injected": sticky_injected,
                    "sticky_skipped": max(sticky_considered - sticky_injected, 0),
                    "sticky_skipped_token_budget": sticky_skipped_token_budget,
                    "max_sticky_memories_in_context": settings.memory_max_sticky_memories_in_context,
                    "max_sticky_context_tokens": settings.memory_max_sticky_context_tokens,
                },
                db_session=self.session,
            )
        return results_out

    # ── Forget with Qdrant cleanup ──────────────────────────────

    async def forget_memory(self, memory_id: uuid.UUID) -> MemoryRecord | None:
        """Archive a memory and remove its vector from Qdrant."""
        record = await self.update(memory_id, is_archived=True)
        if record:
            try:
                store = get_vector_store()
                store.delete_point(str(memory_id))
            except Exception as e:
                logger.warning("Failed to delete point %s from Qdrant: %s", memory_id, e)
            if settings.memory_graph_write_mode == "dual":
                try:
                    async with self.session.begin_nested():
                        from shogun.services.memory_graph_service import MemoryGraphService

                        await MemoryGraphService(self.session).ensure_memory_node(
                            record, update_vector=False
                        )
                except Exception as e:
                    logger.warning("Failed to deprecate MemoryGraph node %s: %s", memory_id, e)
        return record

    # ── Reindex ─────────────────────────────────────────────────

    async def reindex_all(self) -> int:
        """Rebuild the entire Qdrant index from SQLite data."""
        store = get_vector_store()
        store.drop_and_recreate()

        # Fetch all active memories
        result = await self.session.execute(
            select(MemoryRecord).where(MemoryRecord.is_archived.is_(False))
        )
        records = result.scalars().all()

        if not records:
            return 0

        items = []
        for r in records:
            embed_text = f"{r.title}\n\n{r.content}"
            if r.summary:
                embed_text = f"{r.title}\n\n{r.summary}\n\n{r.content}"
            items.append({
                "id": str(r.id),
                "text": embed_text,
                "payload": {
                    "memory_type": r.memory_type,
                    "agent_id": str(r.agent_id),
                    "title": r.title,
                    "importance_score": r.importance_score,
                    "decay_class": r.decay_class,
                    "is_pinned": r.is_pinned,
                    "tags": r.tags or [],
                    "sensitivity": r.sensitivity,
                    "scope_status": r.scope_status,
                    "tenant_id": r.tenant_id,
                    "user_id": r.user_id,
                    "team_id": r.team_id,
                    "workspace_id": r.workspace_id,
                    "project_id": r.project_id,
                    "workflow_id": r.workflow_id,
                    "conversation_provider": r.conversation_provider,
                    "conversation_id": r.conversation_id,
                    "topic_id": r.topic_id,
                    "policy_version": r.policy_version,
                    "graph_node_id": str(r.id),
                    "graph_status": "active" if settings.memory_graph_write_mode == "dual" else "pending",
                },
            })

        count = store.upsert_batch(items)

        # Update qdrant_point_ids
        for r in records:
            r.qdrant_point_id = str(r.id)
        await self.session.flush()

        logger.info("Reindexed %d memories into Qdrant", count)
        return count

    # ── Salience operations ──────────────────────────────────────

    async def record_access(self, memory_id: uuid.UUID) -> MemoryRecord | None:
        """Record that a memory was retrieved as a candidate.

        Increments access_count and updates last_accessed_at.
        Does NOT reinforce relevance — mere retrieval is not confirmation.
        """
        record = await self.get_by_id(memory_id)
        if record is None:
            return None

        record.access_count += 1
        record.last_accessed_at = datetime.now(timezone.utc)
        record.recall_count += 1
        record.last_recalled_at = record.last_accessed_at

        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def reinforce(
        self,
        memory_id: uuid.UUID,
        event_type: str,
        strength: float = 1.0,
    ) -> MemoryRecord | None:
        """Reinforce (or penalize) a memory's relevance based on usage.

        Event types:
        - retrieved_and_used: Memory was injected into context and contributed
        - confirmed_by_operator: Operator explicitly confirmed usefulness
        - reused_across_sessions: Successfully reused in a different session
        - retrieved_not_used: Retrieved but not actually used (mild penalty)
        """
        record = await self.get_by_id(memory_id)
        if record is None:
            return None

        now = datetime.now(timezone.utc)

        # First: apply any pending decay before reinforcement
        decayed = compute_decayed_relevance(
            current_relevance=record.relevance_score,
            decay_class=record.decay_class,
            last_confirmed_at=record.last_confirmed_at,
            is_pinned=record.is_pinned,
            now=now,
        )

        # Then: apply reinforcement on the decayed value
        record.relevance_score = compute_reinforced_relevance(
            current_relevance=decayed,
            event_type=event_type,
            strength=strength,
        )

        # Update tracking
        if event_type != "retrieved_not_used":
            record.successful_use_count += 1
            record.last_confirmed_at = now

        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def get_effective_relevance(self, memory_id: uuid.UUID) -> float | None:
        """Get the current effective relevance (with decay applied)."""
        record = await self.get_by_id(memory_id)
        if record is None:
            return None

        return compute_decayed_relevance(
            current_relevance=record.relevance_score,
            decay_class=record.decay_class,
            last_confirmed_at=record.last_confirmed_at,
            is_pinned=record.is_pinned,
        )

    async def get_recency_boost(self, memory_id: uuid.UUID) -> float | None:
        """Get the current recency boost for a memory."""
        record = await self.get_by_id(memory_id)
        if record is None:
            return None

        return compute_recency_boost(last_accessed_at=record.last_accessed_at)

    # ── Batch operations (for Bushido) ───────────────────────────

    async def apply_decay_batch(
        self, agent_id: uuid.UUID | None = None, limit: int = 500
    ) -> int:
        """Apply time-based decay to memory records in batch.

        Designed to be called by Bushido's nightly consolidation.
        Returns the number of records updated.
        """
        query = select(MemoryRecord).where(
            MemoryRecord.is_pinned.is_(False),
            MemoryRecord.is_archived.is_(False),
            MemoryRecord.decay_class.notin_(["sticky", "pinned"]),
        )
        if agent_id:
            query = query.where(MemoryRecord.agent_id == agent_id)

        query = query.limit(limit)
        result = await self.session.execute(query)
        records = result.scalars().all()

        now = datetime.now(timezone.utc)
        updated = 0

        for record in records:
            old_relevance = record.relevance_score
            new_relevance = compute_decayed_relevance(
                current_relevance=old_relevance,
                decay_class=record.decay_class,
                last_confirmed_at=record.last_confirmed_at,
                is_pinned=False,
                now=now,
            )

            if abs(new_relevance - old_relevance) > 0.001:
                record.relevance_score = new_relevance
                updated += 1

        if updated > 0:
            await self.session.flush()

        return updated

    # ── Query helpers ────────────────────────────────────────────

    async def get_by_agent(
        self,
        agent_id: uuid.UUID,
        memory_type: str | None = None,
        include_archived: bool = False,
    ) -> list[MemoryRecord]:
        """Get all memory records for an agent, optionally filtered by type."""
        query = select(MemoryRecord).where(MemoryRecord.agent_id == agent_id)

        if not include_archived:
            query = query.where(MemoryRecord.is_archived.is_(False))
        if memory_type:
            query = query.where(MemoryRecord.memory_type == memory_type)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_pinned(
        self,
        agent_id: uuid.UUID,
        scope: MemoryScopeEnvelope | dict[str, Any] | None = None,
    ) -> list[MemoryRecord]:
        """Get all pinned memories for an agent."""
        predicates = [
            MemoryRecord.agent_id == agent_id,
            MemoryRecord.is_pinned.is_(True),
            MemoryRecord.is_archived.is_(False),
        ]
        memory_scope = coerce_scope(scope)
        if memory_scope is not None:
            predicates.extend(authorization_predicates(scope=memory_scope, agent_id=agent_id))
        result = await self.session.execute(
            select(MemoryRecord).where(*predicates)
        )
        return list(result.scalars().all())
