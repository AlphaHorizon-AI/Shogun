"""Append-only mission event helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.supermode import MissionEvent


async def append_event(
    session: AsyncSession,
    mission_id: uuid.UUID,
    event_type: str,
    summary: str,
    *,
    task_id: uuid.UUID | None = None,
    agent_id: uuid.UUID | None = None,
    event_data: dict | None = None,
    severity: str = "info",
) -> MissionEvent:
    event = MissionEvent(
        mission_id=mission_id,
        task_id=task_id,
        agent_id=agent_id,
        event_type=event_type.upper(),
        severity=severity,
        summary=summary[:2000],
        event_data=event_data or {},
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    await session.flush()
    return event
