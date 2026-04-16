"""Memory service — metadata CRUD + salience + vector search.

Wraps the memory record ORM model and integrates:
  - SQLite for metadata, salience scores, and lifecycle
  - Qdrant for vector similarity search
  - Salience engine for decay, reinforcement, and reranking
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.memory_record import MemoryRecord
from shogun.engine.memory_salience import (
    ScoredMemory,
    compute_decayed_relevance,
    compute_recency_boost,
    compute_reinforced_relevance,
    rerank_candidates,
)
from shogun.engine.vector_store import get_vector_store
from shogun.services.base_service import BaseService

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
        **kwargs: Any,
    ) -> MemoryRecord:
        """Create a memory with dual-write to SQLite + Qdrant."""
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
                },
            )
            # Store the Qdrant point ID on the record
            record.qdrant_point_id = str(record.id)
            await self.session.flush()
        except Exception as e:
            logger.warning("Failed to upsert memory %s to Qdrant: %s", record.id, e)

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
        limit: int = 20,
        weight_overrides: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        """Hybrid semantic search: Qdrant vector retrieval + salience reranking.

        Returns scored, ranked memory results with full metadata.
        """
        store = get_vector_store()

        # 1. Vector search in Qdrant
        qdrant_hits = store.search(
            query_text=query,
            memory_types=memory_types,
            agent_id=str(agent_id) if agent_id else None,
            min_importance=min_importance,
            pinned_only=pinned_only,
            limit=limit * 2,  # over-fetch for better reranking
        )

        if not qdrant_hits:
            return []

        # 2. Fetch full metadata from SQLite
        hit_ids = [uuid.UUID(h["memory_id"]) for h in qdrant_hits]
        similarity_map = {h["memory_id"]: h["score"] for h in qdrant_hits}

        result = await self.session.execute(
            select(MemoryRecord).where(
                MemoryRecord.id.in_(hit_ids),
                MemoryRecord.is_archived == False,
            )
        )
        records = {str(r.id): r for r in result.scalars().all()}

        # 3. Build scored candidates
        now = datetime.now(timezone.utc)
        candidates: list[ScoredMemory] = []

        for hit in qdrant_hits:
            mid = hit["memory_id"]
            record = records.get(mid)
            if not record:
                continue

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

        # 5. Return top-N with full score breakdown
        return [
            {
                "memory_id": c.memory_id,
                "memory_type": c.memory_type,
                "title": c.title,
                "content": c.content,
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
                "is_pinned": c.is_pinned,
                "last_confirmed_at": c.last_confirmed_at.isoformat() if c.last_confirmed_at else None,
            }
            for c in ranked[:limit]
        ]

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
        return record

    # ── Reindex ─────────────────────────────────────────────────

    async def reindex_all(self) -> int:
        """Rebuild the entire Qdrant index from SQLite data."""
        store = get_vector_store()
        store.drop_and_recreate()

        # Fetch all active memories
        result = await self.session.execute(
            select(MemoryRecord).where(MemoryRecord.is_archived == False)
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
                    "tags": [],
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
            MemoryRecord.is_pinned == False,
            MemoryRecord.is_archived == False,
            MemoryRecord.decay_class != "pinned",
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
            query = query.where(MemoryRecord.is_archived == False)
        if memory_type:
            query = query.where(MemoryRecord.memory_type == memory_type)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_pinned(self, agent_id: uuid.UUID) -> list[MemoryRecord]:
        """Get all pinned memories for an agent."""
        result = await self.session.execute(
            select(MemoryRecord).where(
                MemoryRecord.agent_id == agent_id,
                MemoryRecord.is_pinned == True,
                MemoryRecord.is_archived == False,
            )
        )
        return list(result.scalars().all())
