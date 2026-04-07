"""Memory service — metadata CRUD + salience operations.

Wraps the memory record ORM model and integrates with the salience engine
for decay, reinforcement, and reranking operations.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.memory_record import MemoryRecord
from shogun.engine.memory_salience import (
    compute_decayed_relevance,
    compute_recency_boost,
    compute_reinforced_relevance,
)
from shogun.services.base_service import BaseService


class MemoryService(BaseService[MemoryRecord]):
    """Service for memory record CRUD and salience operations.

    Qdrant vector operations will be integrated in Phase 2.
    This service manages the relational metadata and salience layer.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(MemoryRecord, session)

    # ── Salience operations ──────────────────────────────────

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

    # ── Batch operations (for Bushido) ───────────────────────

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

    # ── Query helpers ────────────────────────────────────────

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
