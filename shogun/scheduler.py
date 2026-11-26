"""AgentFlow Scheduler — APScheduler v3 async integration for scheduled flows."""

from __future__ import annotations

import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def _make_flow_job_id(flow_id: uuid.UUID) -> str:
    return f"agentflow_{flow_id}"


async def _fire_flow_schedule(flow_id: str) -> None:
    """Callback invoked by APScheduler when an AgentFlow schedule fires."""
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
    sched = get_scheduler()
    job_id = _make_flow_job_id(flow.id)

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
        flow.name,
        flow.id,
        frequency,
        time_str,
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
    """Align persisted AgentFlow schedules with APScheduler."""
    from sqlalchemy import select

    from shogun.db.models.agent_flow import AgentFlow

    result = await session.execute(select(AgentFlow).where(AgentFlow.is_deleted.is_(False)))
    flows = result.scalars().all()

    count = 0
    active_job_ids: set[str] = set()
    for flow in flows:
        input_node = next((node for node in flow.nodes if node.node_type == "input"), None)
        if input_node:
            cfg = dict(input_node.config or {})
            if str(cfg.get("input_type") or "").lower() == "scheduled" and (
                flow.trigger_type != "scheduled" or not flow.schedule_config
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
    job = get_scheduler().get_job(job_id)
    return {
        "scheduler_job_id": job_id,
        "scheduler_registered": job is not None,
        "next_run_at": getattr(job, "next_run_time", None) if job else None,
    }


async def start_scheduler() -> None:
    """Start the APScheduler background scheduler for AgentFlows."""
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
    log.info("AgentFlow scheduler started.")


async def stop_scheduler() -> None:
    """Gracefully shut down the APScheduler."""
    sched = get_scheduler()
    if sched.running:
        sched.shutdown(wait=False)
    log.info("AgentFlow scheduler stopped.")
