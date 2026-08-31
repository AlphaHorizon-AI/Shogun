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
from apscheduler.triggers.interval import IntervalTrigger

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

    # Keep persisted schedule state aligned with the live scheduler.
    from sqlalchemy import select

    from shogun.db.engine import async_session_factory
    from shogun.db.models.bushido import BushidoSchedule

    if sid:
        async with async_session_factory() as session:
            schedule = await session.scalar(
                select(BushidoSchedule).where(BushidoSchedule.id == sid)
            )
            if schedule:
                if schedule.frequency == "one-off":
                    schedule.is_enabled = False
                    schedule.next_run_at = None
                else:
                    job = get_scheduler().get_job(_make_job_id(schedule.id))
                    schedule.next_run_at = getattr(job, "next_run_time", None)
                await session.commit()


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
    next_run = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
    if schedule.frequency == "one-off" and next_run is None:
        raise ValueError("One-off schedule must specify a future date and time")

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
    schedule.next_run_at = next_run
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


async def _run_heartbeat() -> None:
    """Background task to run system heartbeat diagnostics and check emails."""
    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent
    from shogun.services.email_service import EmailService
    from shogun.services.event_logger import EventLogger
    from datetime import datetime, timezone

    log.info("System heartbeat firing...")

    async with async_session_factory() as session:
        # 1. Update heartbeat on active agents
        from sqlalchemy import select
        try:
            result = await session.execute(
                select(Agent).where(Agent.is_deleted == False, Agent.status == "active")
            )
            agents = result.scalars().all()
            now = datetime.now(timezone.utc)
            for agent in agents:
                agent.last_heartbeat_at = now
            log.info("Heartbeat updated for %d active agent(s)", len(agents))
        except Exception as exc:
            log.error("Failed to update agent heartbeats: %s", exc)
            agents = []

        # 2. Check email when the account is active and ToolGate allows reads.
        email_sync_success = False
        try:
            email_svc = EmailService(session)
            email_acc = await email_svc.get_account()
            if email_acc and email_acc.is_active:
                # Fetch folders to confirm connection is good
                await email_svc.fetch_folders()
                email_acc.last_sync_at = datetime.now(timezone.utc)
                email_sync_success = True
                log.info("Email account %s checked successfully", email_acc.email_address)
        except Exception as exc:
            log.warning("Email check failed during heartbeat: %s", exc)

        await session.commit()

        # 3. Log a system event
        try:
            await EventLogger.emit_system_event(
                event_type="system.heartbeat",
                action=f"System heartbeat processed. Active agents: {len(agents)}. Email synced: {email_sync_success}",
                detail={
                    "agent_count": len(agents),
                    "email_sync_success": email_sync_success
                }
            )
        except Exception as exc:
            log.warning("Failed to emit heartbeat event: %s", exc)


async def register_heartbeat_job(session) -> None:
    """Read heartbeat frequency from primary Shogun agent settings and schedule heartbeat job."""
    from sqlalchemy import select
    from shogun.db.models.agent import Agent
    from apscheduler.triggers.interval import IntervalTrigger

    sched = get_scheduler()
    if sched.get_job("system_heartbeat"):
        sched.remove_job("system_heartbeat")

    frequency = 15
    try:
        result = await session.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False
            )
        )
        shogun = result.scalars().first()
        if shogun and shogun.bushido_settings:
            frequency = shogun.bushido_settings.get("heartbeat_frequency", 15)
    except Exception as exc:
        log.warning("Failed to read heartbeat frequency from DB, using 15: %s", exc)

    trigger = IntervalTrigger(minutes=frequency)
    sched.add_job(
        _run_heartbeat,
        trigger=trigger,
        id="system_heartbeat",
        replace_existing=True,
        misfire_grace_time=60,
    )
    log.info("System heartbeat scheduled every %d minutes", frequency)


async def reschedule_heartbeat(minutes: int) -> None:
    """Reschedule the heartbeat job dynamically with the new frequency in minutes."""
    sched = get_scheduler()
    if sched.get_job("system_heartbeat"):
        sched.remove_job("system_heartbeat")

    from apscheduler.triggers.interval import IntervalTrigger
    trigger = IntervalTrigger(minutes=minutes)
    sched.add_job(
        _run_heartbeat,
        trigger=trigger,
        id="system_heartbeat",
        replace_existing=True,
        misfire_grace_time=60,
    )
    log.info("Rescheduled system heartbeat to run every %d minutes", minutes)


async def sync_all_schedules(session) -> int:
    """Load all BushidoSchedule rows from DB and sync APScheduler.

    Called on startup. Returns number of enabled schedules registered.
    """
    try:
        await register_heartbeat_job(session)
    except Exception as exc:
        log.warning("Failed to register system heartbeat job: %s", exc)

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

    # ── Also sync Agent Flow schedules ────────────────────────
    try:
        flow_count = await sync_flow_schedules(session)
        log.info("AgentFlow: synced %d flow schedules with APScheduler", flow_count)
    except Exception as exc:
        log.warning("AgentFlow: failed to sync flow schedules: %s", exc)

    await session.commit()
    return count


# ── Agent Flow Schedule Support ──────────────────────────────



# ── Agent Flow Schedule Support ──────────────────────────────


def _make_flow_job_id(flow_id: uuid.UUID) -> str:
    return f"agentflow_{flow_id}"


async def _fire_flow_schedule(flow_id: str) -> None:
    """Callback invoked by APScheduler when a flow schedule fires."""
    from shogun.engine.flow_engine import start_flow_run

    log.info("AgentFlow scheduler firing: flow_id=%s", flow_id)
    try:
        fid = uuid.UUID(flow_id)
    except ValueError:
        log.error("AgentFlow scheduler: invalid flow_id '%s'", flow_id)
        return

    try:
        await start_flow_run(fid, trigger_type="scheduled")
    except Exception:
        log.exception("AgentFlow scheduled execution failed for %s", flow_id)


async def register_flow_schedule(flow) -> dict:
    """Register an Agent Flow with APScheduler based on its schedule_config."""
    from apscheduler.triggers.cron import CronTrigger
    sched = get_scheduler()
    job_id = _make_flow_job_id(flow.id)

    # Remove existing
    if sched.get_job(job_id):
        sched.remove_job(job_id)

    if flow.trigger_type != "scheduled" or flow.status != "active":
        return scheduler_job_snapshot(job_id)

    schedule_config = flow.schedule_config or {}
    frequency = schedule_config.get("frequency") or schedule_config.get("schedule_frequency") or "nightly"
    time_str = schedule_config.get("schedule_time", "02:00")

    try:
        hour, minute = (int(x) for x in time_str.split(":"))
    except (ValueError, AttributeError):
        hour, minute = 2, 0

    if frequency == "hourly":
        offset = schedule_config.get("minute_offset") or schedule_config.get("schedule_minute_offset") or 0
        trigger = CronTrigger(minute=offset)
    elif frequency == "nightly":
        trigger = CronTrigger(hour=hour, minute=minute)
    elif frequency == "weekly":
        days = schedule_config.get("schedule_days", ["mon"])
        trigger = CronTrigger(day_of_week=",".join(days), hour=hour, minute=minute)
    elif frequency == "monthly":
        day = schedule_config.get("schedule_day", 1)
        trigger = CronTrigger(day=day, hour=hour, minute=minute)
    else:
        trigger = CronTrigger(hour=hour, minute=minute)

    sched.add_job(
        _fire_flow_schedule,
        trigger=trigger,
        id=job_id,
        kwargs={"flow_id": str(flow.id)},
        replace_existing=True,
        misfire_grace_time=120,
    )
    snapshot = scheduler_job_snapshot(job_id)
    if not snapshot["scheduler_registered"]:
        raise RuntimeError(f"APScheduler did not retain AgentFlow job {job_id}")
    log.info(
        "AgentFlow: registered schedule for '%s' (%s) — freq=%s at %s",
        flow.name, flow.id, frequency, time_str,
    )
    return snapshot


async def deregister_flow_schedule(flow_id: uuid.UUID) -> None:
    """Remove a flow schedule from APScheduler."""
    sched = get_scheduler()
    job_id = _make_flow_job_id(flow_id)
    if sched.get_job(job_id):
        sched.remove_job(job_id)
        log.info("AgentFlow: deregistered schedule for flow %s", flow_id)


async def sync_flow_schedules(session, *, missing_only: bool = False) -> int:
    """Align persisted AgentFlow schedules with APScheduler.

    ``missing_only`` repairs lost jobs without continuously replacing healthy
    cron jobs around their firing time.
    """
    from sqlalchemy import select
    from shogun.db.models.agent_flow import AgentFlow

    result = await session.execute(
        select(AgentFlow).where(AgentFlow.is_deleted == False)
    )
    flows = result.scalars().all()

    count = 0
    active_job_ids: set[str] = set()
    for flow in flows:
        input_node = next((node for node in flow.nodes if node.node_type == "input"), None)
        if input_node:
            cfg = dict(input_node.config or {})
            if (
                str(cfg.get("input_type") or "").lower() == "scheduled"
                and (
                    flow.trigger_type != "scheduled"
                    or not flow.schedule_config
                )
            ):
                frequency = cfg.get("schedule_frequency") or cfg.get("frequency") or "nightly"
                sch_cfg = {
                    "frequency": frequency,
                    "schedule_time": cfg.get("schedule_time") or "07:00",
                }
                if frequency == "weekly":
                    sch_cfg["schedule_days"] = cfg.get("schedule_days") or ["mon", "tue", "wed", "thu", "fri"]
                elif frequency == "monthly":
                    sch_cfg["schedule_day"] = int(cfg.get("schedule_day") or 1)
                elif frequency == "hourly":
                    sch_cfg["minute_offset"] = int(cfg.get("minute_offset") or cfg.get("schedule_minute_offset") or 0)
                flow.trigger_type = "scheduled"
                flow.schedule_config = sch_cfg
                if flow.status == "draft":
                    flow.status = "active"

        if flow.trigger_type == "scheduled" and flow.status == "active":
            job_id = _make_flow_job_id(flow.id)
            active_job_ids.add(job_id)
            try:
                if not missing_only or get_scheduler().get_job(job_id) is None:
                    await register_flow_schedule(flow)
                count += 1
            except Exception as exc:
                log.warning("AgentFlow: failed to register schedule for flow %s: %s", flow.id, exc)

    for job in list(get_scheduler().get_jobs()):
        if (
            job.id.startswith("agentflow_")
            and job.id != "agentflow_schedule_reconcile"
            and job.id not in active_job_ids
        ):
            get_scheduler().remove_job(job.id)
            log.info("AgentFlow: removed stale scheduler job %s", job.id)

    await session.flush()
    return count


async def _reconcile_flow_schedules() -> None:
    """Repair missing AgentFlow jobs using a fresh database session."""
    from shogun.db.engine import async_session_factory

    try:
        async with async_session_factory() as session:
            await sync_flow_schedules(session, missing_only=True)
            await session.commit()
    except Exception:
        log.exception("AgentFlow schedule reconciliation failed")


def scheduler_job_snapshot(job_id: str) -> dict:
    """Return transparent live registration state for a scheduler job."""
    job = get_scheduler().get_job(job_id)
    return {
        "scheduler_job_id": job_id,
        "scheduler_registered": job is not None,
        "next_run_at": getattr(job, "next_run_time", None) if job else None,
    }


# ── Lifecycle ────────────────────────────────────────────────

async def start_scheduler() -> None:
    """Start the APScheduler background scheduler."""
    sched = get_scheduler()
    if not sched.running:
        sched.start()
    sched.add_job(
        _reconcile_flow_schedules,
        trigger=IntervalTrigger(minutes=1),
        id="agentflow_schedule_reconcile",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    from shogun.services.reminder_service import process_due_reminders
    sched.add_job(
        process_due_reminders,
        trigger=IntervalTrigger(minutes=1),
        id="bushido_reminder_due_scanner",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
    # APScheduler is only a wake-up mechanism. Durable mission/task state,
    # leases, and wake times remain authoritative in SQL.
    from shogun.supermode.supervisor import supervisor_tick
    sched.add_job(
        supervisor_tick,
        trigger=IntervalTrigger(seconds=10),
        id="supermode_mission_supervisor",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=30,
        next_run_time=datetime.now(timezone.utc),
    )
    log.info("Bushido scheduler started.")


async def stop_scheduler() -> None:
    """Gracefully shut down the APScheduler."""
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
    log.info("Bushido scheduler stopped.")
