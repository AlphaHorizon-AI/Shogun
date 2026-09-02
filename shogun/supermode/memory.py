"""Governed long-term memory recall for Supermode missions."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.agent import Agent
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.mission import Mission
from shogun.services.memory_service import MemoryService
from shogun.supermode.events import append_event

log = logging.getLogger("shogun.supermode.memory")


async def _fallback_supermode_memories(
    session: AsyncSession,
    *,
    primary_agent_id: uuid.UUID,
    owner_user_id: str,
    team_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    records = list(
        (
            await session.scalars(
                select(MemoryRecord)
                .where(
                    MemoryRecord.agent_id == primary_agent_id,
                    MemoryRecord.is_archived.is_(False),
                    MemoryRecord.importance_score >= 0.55,
                )
                .order_by(MemoryRecord.importance_score.desc(), MemoryRecord.created_at.desc())
                .limit(50)
            )
        ).all()
    )
    visible_records = [
        record
        for record in records
        if "supermode" in set(record.tags or [])
        and (not record.user_id or record.user_id == owner_user_id)
        and (not record.team_id or record.team_id == team_id)
    ]
    return [
        {
            "memory_id": str(record.id),
            "title": record.title,
            "content": record.content,
            "summary": record.summary,
            "memory_type": record.memory_type,
            "importance_score": record.importance_score,
            "confidence_score": record.confidence_score,
            "scores": {"final": record.importance_score},
        }
        for record in visible_records
    ][:limit]


async def recall_relevant_memories(
    session: AsyncSession,
    mission: Mission,
    *,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Recall prior Supermode learnings and persist a compact context snapshot."""
    primary = await session.scalar(
        select(Agent).where(
            Agent.agent_type == "shogun",
            Agent.is_primary.is_(True),
            Agent.is_deleted.is_(False),
        )
    )
    if primary is None:
        return []

    memory_service = MemoryService(session)
    try:
        results = await memory_service.search(
            mission.objective or mission.title,
            agent_id=primary.id,
            memory_types=["procedural", "semantic"],
            min_importance=0.55,
            limit=limit * 2,
            scope={"user_id": mission.owner_user_id, "team_id": mission.team_id},
        )
        result_ids = [uuid.UUID(str(item["memory_id"])) for item in results if item.get("memory_id")]
        tagged_records = {
            record.id
            for record in (
                await session.scalars(select(MemoryRecord).where(MemoryRecord.id.in_(result_ids)))
            ).all()
            if "supermode" in set(record.tags or [])
        } if result_ids else set()
        results = [item for item in results if uuid.UUID(str(item["memory_id"])) in tagged_records][:limit]
        if not results:
            results = await _fallback_supermode_memories(
                session,
                primary_agent_id=primary.id,
                owner_user_id=mission.owner_user_id,
                team_id=mission.team_id,
                limit=limit,
            )
    except Exception as exc:
        log.warning("Semantic Supermode memory recall failed; using SQLite fallback: %s", exc)
        results = await _fallback_supermode_memories(
            session,
            primary_agent_id=primary.id,
            owner_user_id=mission.owner_user_id,
            team_id=mission.team_id,
            limit=limit,
        )

    compact: list[dict[str, Any]] = []
    remaining_chars = 6000
    for item in results:
        if remaining_chars <= 0:
            break
        content = str(item.get("summary") or item.get("content") or "").strip()
        if not content:
            continue
        content = content[: min(1200, remaining_chars)]
        remaining_chars -= len(content)
        memory_id = uuid.UUID(str(item["memory_id"]))
        compact.append(
            {
                "memory_id": str(memory_id),
                "title": str(item.get("title") or "Prior Supermode learning")[:500],
                "content": content,
                "memory_type": str(item.get("memory_type") or "semantic"),
                "relevance": float((item.get("scores") or {}).get("final") or item.get("importance_score") or 0),
                "confidence": float(item.get("confidence_score") or 0),
            }
        )
        try:
            await memory_service.record_access(memory_id)
        except Exception as exc:
            log.warning("Could not update access metadata for recalled memory %s: %s", memory_id, exc)

    if compact:
        mission.input_payload = {
            **(mission.input_payload or {}),
            "recalled_memories": compact,
        }
        await append_event(
            session,
            mission.id,
            "MEMORY_RECALLED",
            f"Recalled {len(compact)} relevant learning(s) for mission planning",
            event_data={"memory_ids": [item["memory_id"] for item in compact]},
        )
    return compact
