"""APScheduler-triggered durable Supermode supervisor.

SQL is the source of truth.  A tick claims bounded work with leases, dispatches
short-lived workers, checkpoints their results, and returns.  No mission is an
in-memory multi-day asyncio task.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update

from shogun.db.engine import async_session_factory
from shogun.db.models.mission import Mission
from shogun.db.models.supermode import MissionAgent, MissionTask
from shogun.supermode.events import append_event
from shogun.supermode.planner import create_initial_plan
from shogun.supermode.state_machine import RUNNABLE_STATES, transition_mission
from shogun.supermode.worker import run_claimed_task, update_mission_progress_and_completion

log = logging.getLogger("shogun.supermode.supervisor")
SUPERVISOR_OWNER = f"{socket.gethostname()}:{uuid.uuid4().hex[:10]}"
LEASE_SECONDS = 600


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    """Normalize SQLite's naive DateTime values for portable comparisons."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def recover_stale_tasks() -> int:
    """Return abandoned leased tasks to READY after a process restart."""
    now = _now()
    recovered = 0
    async with async_session_factory() as session:
        stale = list(
            (
                await session.scalars(
                    select(MissionTask).where(
                        MissionTask.status == "running",
                        MissionTask.lease_expires_at.is_not(None),
                        MissionTask.lease_expires_at < now,
                    )
                )
            ).all()
        )
        for task in stale:
            task.status = "ready"
            task.retry_count += 1
            task.lease_owner = None
            task.lease_expires_at = None
            task.heartbeat_at = now
            agent = await session.get(MissionAgent, task.assigned_agent_id) if task.assigned_agent_id else None
            if agent and agent.status == "active":
                agent.status = "waiting"
                agent.current_task_id = None
            await append_event(
                session,
                task.mission_id,
                "TASK_RETRIED",
                f"Recovered stale lease for {task.title}",
                task_id=task.id,
                agent_id=task.assigned_agent_id,
                event_data={"reason": "stale_lease", "retry_count": task.retry_count},
                severity="warn",
            )
            recovered += 1
        await session.commit()
    return recovered


async def _enforce_live_governance(mission_id: uuid.UUID, posture: dict) -> bool:
    async with async_session_factory() as session:
        mission = await session.get(Mission, mission_id)
        if not mission:
            return False
        tier = str(posture.get("active_tier") or "tactical").lower()
        kill_switch = bool(posture.get("kill_switch_active"))
        if kill_switch:
            if mission.status not in {"paused_harakiri", "completed", "failed", "cancelled"}:
                await transition_mission(
                    session,
                    mission,
                    "paused_harakiri",
                    reason="Mission paused because HARAKIRI is active",
                    event_type="MISSION_HARAKIRI_PAUSED",
                    event_data={"posture": tier},
                )
                await session.commit()
            return False
        if tier not in {"campaign", "ronin"}:
            if mission.status not in {"paused_posture", "paused", "completed", "failed", "cancelled"}:
                await transition_mission(
                    session,
                    mission,
                    "paused_posture",
                    reason=f"Supermode requires Campaign or Ronin; current posture is {tier.upper()}",
                    event_type="MISSION_POSTURE_PAUSED",
                    event_data={"posture": tier},
                )
                await session.commit()
            return False
        if mission.status in {"paused_posture", "paused_harakiri"}:
            target = "planning" if mission.current_plan_version == 0 else "running"
            await transition_mission(
                session,
                mission,
                target,
                reason=f"Eligible live posture restored: {tier.upper()}",
                event_type="MISSION_RESUMED",
                event_data={"posture": tier},
            )
            await session.commit()
        return mission.status in RUNNABLE_STATES


async def _prepare_mission(mission_id: uuid.UUID) -> bool:
    async with async_session_factory() as session:
        mission = await session.get(Mission, mission_id)
        if not mission:
            return False
        now = _now()
        if (
            mission.deadline_at
            and _as_utc(mission.deadline_at) <= now
            and mission.status in RUNNABLE_STATES
        ):
            await transition_mission(
                session,
                mission,
                "paused_budget",
                reason="Mission deadline reached",
                event_type="MISSION_PAUSED_BUDGET",
            )
            await session.commit()
            return False
        if mission.status == "planning" and mission.current_plan_version == 0:
            await create_initial_plan(session, mission)
            await transition_mission(
                session,
                mission,
                "running",
                reason="Initial durable plan is ready",
                event_type="MISSION_STARTED",
            )
        elif mission.status == "replanning":
            await transition_mission(session, mission, "running", reason="Revised plan is ready")
        elif mission.status == "waiting":
            if mission.next_wake_at and _as_utc(mission.next_wake_at) > now:
                return False
            await transition_mission(session, mission, "running", reason="Mission wake condition reached")
        if mission.status != "running":
            await session.commit()
            return False

        tasks = list(
            (await session.scalars(select(MissionTask).where(MissionTask.mission_id == mission.id))).all()
        )
        states = {str(task.id): task.status for task in tasks}
        for task in tasks:
            if (
                task.status == "waiting"
                and task.next_wake_at
                and _as_utc(task.next_wake_at) <= now
            ):
                task.status = "ready"
                task.next_wake_at = None
                task.blocked_reason = None
            if task.status not in {"pending", "blocked_dependency"}:
                continue
            deps = [states.get(str(value)) for value in (task.depends_on_task_ids or [])]
            if any(state in {"failed", "cancelled"} for state in deps):
                task.status = "blocked_dependency"
                task.blocked_reason = "A required predecessor failed or was cancelled"
            elif all(state == "completed" for state in deps):
                task.status = "ready"
                task.blocked_reason = None
        await session.commit()
        return True


async def _claim_tasks(mission_id: uuid.UUID) -> list[uuid.UUID]:
    now = _now()
    lease_expires = now + timedelta(seconds=LEASE_SECONDS)
    claimed: list[uuid.UUID] = []
    async with async_session_factory() as session:
        mission = await session.get(Mission, mission_id)
        if not mission or mission.status != "running":
            return []
        running_count = int(
            (
                await session.scalar(
                    select(func.count(MissionTask.id)).where(
                        MissionTask.mission_id == mission.id, MissionTask.status == "running"
                    )
                )
            )
            or 0
        )
        slots = max(0, mission.max_parallel_agents - running_count)
        if slots == 0:
            return []
        candidates = list(
            (
                await session.scalars(
                    select(MissionTask)
                    .where(MissionTask.mission_id == mission.id, MissionTask.status == "ready")
                    .order_by(MissionTask.priority.desc(), MissionTask.created_at)
                    .limit(slots)
                )
            ).all()
        )
        for task in candidates:
            attempt_id = uuid.uuid4().hex
            result = await session.execute(
                update(MissionTask)
                .where(MissionTask.id == task.id, MissionTask.status == "ready")
                .values(
                    status="running",
                    lease_owner=SUPERVISOR_OWNER,
                    lease_expires_at=lease_expires,
                    heartbeat_at=now,
                    execution_attempt_id=attempt_id,
                    idempotency_key=f"{mission.id}:{task.id}:{attempt_id}",
                    started_at=func.coalesce(MissionTask.started_at, now),
                )
            )
            if result.rowcount:
                claimed.append(task.id)
        await session.commit()
    return claimed


async def supervisor_tick() -> None:
    """Run one restart-safe supervisor cycle."""
    try:
        await recover_stale_tasks()
        from shogun.services.posture_guard import get_posture_tool_filter

        posture = await get_posture_tool_filter()
        async with async_session_factory() as session:
            mission_ids = list(
                (
                    await session.scalars(
                        select(Mission.id).where(
                            Mission.is_supermode.is_(True),
                            Mission.status.in_([
                                *RUNNABLE_STATES,
                                "paused_posture",
                                "paused_harakiri",
                            ]),
                        )
                    )
                ).all()
            )
        for mission_id in mission_ids:
            if not await _enforce_live_governance(mission_id, posture):
                continue
            if not await _prepare_mission(mission_id):
                continue
            claimed = await _claim_tasks(mission_id)
            if claimed:
                await asyncio.gather(*(run_claimed_task(task_id) for task_id in claimed), return_exceptions=True)
            await update_mission_progress_and_completion(mission_id)
    except Exception:
        log.exception("Supermode supervisor tick failed")
