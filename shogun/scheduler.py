"""Bushido Scheduler — APScheduler v3 async integration.

APScheduler 3.11.x uses AsyncIOScheduler (not AsyncScheduler which is v4).
Uses asyncio event loop for non-blocking schedule management.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

if TYPE_CHECKING:
    from shogun.db.models.bushido import BushidoSchedule

log = logging.getLogger(__name__)

# ── Singleton ────────────────────────────────────────────────
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


# ── Trigger builder ──────────────────────────────────────────

def build_trigger(schedule: "BushidoSchedule"):
    """Convert a BushidoSchedule row to an APScheduler trigger."""
    freq = schedule.frequency
    time_str = schedule.schedule_time or "02:00"
    hour, minute = (int(x) for x in time_str.split(":"))

    if freq == "one-off":
        if schedule.schedule_datetime:
            try:
                run_at = datetime.fromisoformat(schedule.schedule_datetime)
            except ValueError:
                run_at = datetime.now(timezone.utc)
        else:
            run_at = datetime.now(timezone.utc)
        return DateTrigger(run_date=run_at)

    elif freq == "hourly":
        offset = schedule.minute_offset or 0
        return CronTrigger(minute=offset)

    elif freq == "nightly":
        return CronTrigger(hour=hour, minute=minute)

    elif freq == "weekly":
        days = schedule.schedule_days or ["mon"]
        day_of_week = ",".join(days)
        return CronTrigger(day_of_week=day_of_week, hour=hour, minute=minute)

    elif freq == "monthly":
        day = schedule.schedule_day or 1
        return CronTrigger(day=day, hour=hour, minute=minute)

    else:
        log.warning("Unknown frequency %r for schedule %s — defaulting to daily midnight", freq, schedule.id)
        return CronTrigger(hour=0, minute=0)


# ── Stable job ID ─────────────────────────────────────────────

def _make_job_id(schedule_id: uuid.UUID) -> str:
    return f"bushido_{schedule_id}"


# ── Job callback ─────────────────────────────────────────────

async def _fire_schedule(
    schedule_id: str,
    job_type: str,
    scope: dict,
    task_instruction: str | None,
    dry_run: bool,
) -> None:
    """Callback invoked by APScheduler when a schedule fires."""
    from shogun.services.bushido_engine import run_job

    log.info("Bushido scheduler firing: job_type=%s schedule=%s", job_type, schedule_id)
    try:
        sid = uuid.UUID(schedule_id)
    except ValueError:
        sid = None

    await run_job(
        job_type=job_type,
        scope=scope,
        trigger_mode="scheduled",
        schedule_id=sid,
        task_instruction=task_instruction,
        dry_run=dry_run,
    )


# ── Schedule management ──────────────────────────────────────

async def register_schedule(schedule: "BushidoSchedule") -> None:
    """Add (or replace) a single schedule in APScheduler."""
    sched = get_scheduler()
    job_id = _make_job_id(schedule.id)

    # Remove existing job with same ID if present
    if sched.get_job(job_id):
        sched.remove_job(job_id)

    if not schedule.is_enabled:
        log.debug("Bushido: schedule %s is disabled — not registering", schedule.id)
        return

    trigger = build_trigger(schedule)

    sched.add_job(
        _fire_schedule,
        trigger=trigger,
        id=job_id,
        kwargs={
            "schedule_id": str(schedule.id),
            "job_type": schedule.job_type,
            "scope": schedule.scope or {},
            "task_instruction": schedule.task_instruction,
            "dry_run": schedule.dry_run,
        },
        replace_existing=True,
        misfire_grace_time=60,
    )
    log.info(
        "Bushido: registered schedule '%s' (%s) — freq=%s",
        schedule.name, schedule.id, schedule.frequency,
    )


async def deregister_schedule(schedule_id: uuid.UUID) -> None:
    """Remove a schedule from APScheduler (does not touch the DB)."""
    sched = get_scheduler()
    job_id = _make_job_id(schedule_id)
    if sched.get_job(job_id):
        sched.remove_job(job_id)
        log.info("Bushido: deregistered schedule %s", schedule_id)
    else:
        log.debug("Bushido: schedule %s not in APScheduler (already absent)", schedule_id)


async def sync_all_schedules(session) -> int:
    """Load all BushidoSchedule rows from DB and sync APScheduler.

    Called on startup. Returns number of enabled schedules registered.
    """
    from sqlalchemy import select
    from shogun.db.models.bushido import BushidoSchedule

    result = await session.execute(select(BushidoSchedule))
    schedules = result.scalars().all()

    count = 0
    for schedule in schedules:
        try:
            await register_schedule(schedule)
            if schedule.is_enabled:
                count += 1
        except Exception as exc:
            log.warning("Bushido: failed to register schedule %s: %s", schedule.id, exc)

    log.info("Bushido: synced %d/%d schedules with APScheduler", count, len(schedules))
    return count


# ── Lifecycle ────────────────────────────────────────────────

async def start_scheduler() -> None:
    """Start the APScheduler background scheduler."""
    sched = get_scheduler()
    if not sched.running:
        sched.start()
    log.info("Bushido scheduler started.")


async def stop_scheduler() -> None:
    """Gracefully shut down the APScheduler."""
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
    log.info("Bushido scheduler stopped.")
