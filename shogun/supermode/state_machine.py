"""Validated mission state transitions.

Keeping transitions centralized prevents an API handler or worker failure from
silently placing a durable mission in a state the recovery loop cannot handle.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.mission import Mission
from shogun.supermode.events import append_event

TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})
RUNNABLE_STATES = frozenset(
    {"planning", "running", "waiting", "replanning", "completing", "learning"}
)

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "draft": frozenset({"planning", "cancelled"}),
    "queued": frozenset({"planning", "running", "cancelled"}),
    "planning": frozenset(
        {
            "running",
            "failed",
            "cancelled",
            "paused",
            "paused_posture",
            "paused_budget",
            "paused_harakiri",
        }
    ),
    "running": frozenset(
        {
            "waiting",
            "blocked_user",
            "blocked_approval",
            "replanning",
            "paused",
            "paused_posture",
            "paused_budget",
            "paused_harakiri",
            "completing",
            "failed",
            "cancelled",
        }
    ),
    "waiting": frozenset({"running", "paused", "paused_posture", "paused_harakiri", "cancelled", "failed"}),
    "blocked_user": frozenset({"running", "replanning", "paused", "cancelled", "failed"}),
    "blocked_approval": frozenset({"running", "paused", "cancelled", "failed"}),
    "replanning": frozenset(
        {
            "running",
            "failed",
            "cancelled",
            "paused",
            "paused_posture",
            "paused_budget",
            "paused_harakiri",
        }
    ),
    "paused": frozenset({"running", "planning", "replanning", "cancelled"}),
    "paused_posture": frozenset({"running", "planning", "replanning", "paused_harakiri", "cancelled"}),
    "paused_budget": frozenset({"running", "replanning", "cancelled"}),
    "paused_harakiri": frozenset({"paused_posture", "running", "planning", "cancelled"}),
    "completing": frozenset({"learning", "replanning", "failed", "cancelled"}),
    "learning": frozenset({"completed", "failed", "cancelled"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
}


class InvalidMissionTransitionError(ValueError):
    pass


async def transition_mission(
    session: AsyncSession,
    mission: Mission,
    target: str,
    *,
    reason: str,
    event_type: str | None = None,
    event_data: dict | None = None,
) -> Mission:
    current = str(mission.status).lower()
    target = target.lower()
    if target == current:
        return mission
    if target not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise InvalidMissionTransitionError(f"Mission cannot transition from {current} to {target}")

    now = datetime.now(timezone.utc)
    mission.status = target
    mission.last_activity_at = now
    if target == "running" and mission.started_at is None:
        mission.started_at = now
    if target in TERMINAL_STATES:
        mission.completed_at = now
    await append_event(
        session,
        mission.id,
        event_type or f"MISSION_{target.upper()}",
        reason,
        event_data={"from": current, "to": target, **(event_data or {})},
        severity="error" if target == "failed" else "info",
    )
    return mission
