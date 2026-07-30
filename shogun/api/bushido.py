"""Bushido routes — reflection, maintenance, and self-improvement."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import (
    get_agent_service,
    get_bushido_job_service,
    get_bushido_recommendation_service,
    get_bushido_schedule_service,
    get_db,
)
from shogun.schemas.bushido import (
    BushidoJobResponse,
    BushidoRecommendationResponse,
    BushidoRunRequest,
    BushidoScheduleCreate,
    BushidoScheduleResponse,
    BushidoScheduleUpdate,
    ReminderCreate,
    ReminderParseRequest,
    ReminderResponse,
    ReminderRunResponse,
    ReminderSnoozeRequest,
    ReminderUpdate,
)
from shogun.schemas.common import ApiResponse
from shogun.services.agent_service import AgentService
from shogun.services.bushido_service import (
    BushidoJobService,
    BushidoRecommendationService,
    BushidoScheduleService,
)
from shogun.services.reminder_service import ReminderService, parse_reminder_text

router = APIRouter(prefix="/bushido", tags=["Bushido"])

# ── Default calibration values ────────────────────────────────
DEFAULT_CALIBRATION = {
    "reflection_intensity": 70,
    "consolidation_rate": 45,
    "exploration_variance": 24,
    "heartbeat_frequency": 15,
}


# ── Stats ────────────────────────────────────────────────────

@router.get("/stats", response_model=ApiResponse)
async def get_bushido_stats(
    job_svc: BushidoJobService = Depends(get_bushido_job_service),
    rec_svc: BushidoRecommendationService = Depends(get_bushido_recommendation_service),
):
    """Compute live Bushido dashboard metrics from real data."""
    from sqlalchemy import select, func
    from shogun.db.models.bushido import BushidoJob, BushidoRecommendation
    from datetime import timedelta

    session = job_svc.session
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # Total completed jobs (all time)
    total_result = await session.execute(
        select(func.count(BushidoJob.id)).where(BushidoJob.status == "completed")
    )
    active_cycles = total_result.scalar() or 0

    # Jobs in the last 30 days
    recent_result = await session.execute(
        select(
            func.count(BushidoJob.id).label("total"),
        ).where(BushidoJob.created_at >= thirty_days_ago)
    )
    recent_total = recent_result.scalar() or 0

    recent_completed = await session.execute(
        select(func.count(BushidoJob.id)).where(
            BushidoJob.created_at >= thirty_days_ago,
            BushidoJob.status == "completed",
        )
    )
    recent_ok = recent_completed.scalar() or 0

    # Avg Fit Quality = success rate of recent jobs
    fit_quality = round((recent_ok / recent_total * 100), 1) if recent_total > 0 else 100.0

    # Recommendations stats
    total_recs = await session.execute(
        select(func.count(BushidoRecommendation.id))
    )
    recs_total = total_recs.scalar() or 0

    approved_recs = await session.execute(
        select(func.count(BushidoRecommendation.id)).where(
            BushidoRecommendation.status == "approved"
        )
    )
    recs_approved = approved_recs.scalar() or 0

    # Optimization delta = improvement from acting on recommendations
    opt_delta = round((recs_approved / recs_total * 100), 1) if recs_total > 0 else 0.0

    # Running jobs (neural load)
    running_result = await session.execute(
        select(func.count(BushidoJob.id)).where(BushidoJob.status == "running")
    )
    running_count = running_result.scalar() or 0
    neural_load = min(running_count * 25, 100)  # 25% per concurrent job, max 100%

    # Engine status based on most recent job
    last_job_result = await session.execute(
        select(BushidoJob.status).order_by(BushidoJob.created_at.desc()).limit(1)
    )
    last_status = last_job_result.scalar()
    engine_status = "synchronized" if last_status in ("completed", None) else "degraded"

    return ApiResponse(data={
        "fit_quality": fit_quality,
        "active_cycles": active_cycles,
        "optimization_delta": opt_delta,
        "neural_load": neural_load,
        "engine_status": engine_status,
        "recent_jobs_total": recent_total,
        "recent_jobs_completed": recent_ok,
        "recommendations_total": recs_total,
        "recommendations_approved": recs_approved,
        "running_jobs": running_count,
    })


# ── Calibration ──────────────────────────────────────────────

@router.get("/calibration", response_model=ApiResponse)
async def get_calibration(
    agent_svc: AgentService = Depends(get_agent_service),
):
    """Get current Bushido calibration settings."""
    from shogun.db.models.agent import Agent
    filters = [Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False]
    records, _ = await agent_svc.get_all(filters=filters)

    if not records:
        return ApiResponse(data=DEFAULT_CALIBRATION)

    settings = records[0].bushido_settings or {}
    return ApiResponse(data={
        "reflection_intensity": settings.get("reflection_intensity", DEFAULT_CALIBRATION["reflection_intensity"]),
        "consolidation_rate": settings.get("consolidation_rate", DEFAULT_CALIBRATION["consolidation_rate"]),
        "exploration_variance": settings.get("exploration_variance", DEFAULT_CALIBRATION["exploration_variance"]),
        "heartbeat_frequency": settings.get("heartbeat_frequency", DEFAULT_CALIBRATION["heartbeat_frequency"]),
    })


@router.put("/calibration", response_model=ApiResponse)
async def save_calibration(
    body: dict,
    agent_svc: AgentService = Depends(get_agent_service),
):
    """Save Bushido calibration settings to the Shogun's bushido_settings."""
    from shogun.db.models.agent import Agent
    import logging
    log = logging.getLogger(__name__)

    filters = [Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False]
    records, _ = await agent_svc.get_all(filters=filters)

    if not records:
        raise HTTPException(status_code=404, detail="Primary Shogun agent not found")

    shogun = records[0]
    current = shogun.bushido_settings or {}
    # Merge calibration values into existing settings
    current["reflection_intensity"] = body.get("reflection_intensity", current.get("reflection_intensity", 70))
    current["consolidation_rate"] = body.get("consolidation_rate", current.get("consolidation_rate", 45))
    current["exploration_variance"] = body.get("exploration_variance", current.get("exploration_variance", 24))
    current["heartbeat_frequency"] = body.get("heartbeat_frequency", current.get("heartbeat_frequency", 15))

    await agent_svc.update(shogun.id, bushido_settings=current)

    # Reschedule heartbeat job dynamically
    from shogun.scheduler import reschedule_heartbeat
    try:
        await reschedule_heartbeat(current["heartbeat_frequency"])
    except Exception as exc:
        log.warning("Failed to reschedule heartbeat on save: %s", exc)

    return ApiResponse(data={
        "reflection_intensity": current["reflection_intensity"],
        "consolidation_rate": current["consolidation_rate"],
        "exploration_variance": current["exploration_variance"],
        "heartbeat_frequency": current["heartbeat_frequency"],
        "message": "Calibration saved.",
    })


@router.post("/calibration/reset", response_model=ApiResponse)
async def reset_calibration(
    agent_svc: AgentService = Depends(get_agent_service),
):
    """Reset Bushido calibration to baseline defaults."""
    from shogun.db.models.agent import Agent
    import logging
    log = logging.getLogger(__name__)

    filters = [Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False]
    records, _ = await agent_svc.get_all(filters=filters)

    if not records:
        raise HTTPException(status_code=404, detail="Primary Shogun agent not found")

    shogun = records[0]
    current = shogun.bushido_settings or {}
    current.update(DEFAULT_CALIBRATION)
    await agent_svc.update(shogun.id, bushido_settings=current)

    # Reschedule heartbeat job back to default
    from shogun.scheduler import reschedule_heartbeat
    try:
        await reschedule_heartbeat(DEFAULT_CALIBRATION["heartbeat_frequency"])
    except Exception as exc:
        log.warning("Failed to reschedule heartbeat on reset: %s", exc)

    return ApiResponse(data={
        **DEFAULT_CALIBRATION,
        "message": "Calibration reset to baseline.",
    })

# ── Jobs ─────────────────────────────────────────────────────


@router.get("/jobs", response_model=ApiResponse)
async def list_jobs(svc: BushidoJobService = Depends(get_bushido_job_service)):
    records, total = await svc.get_all(limit=100)
    return ApiResponse(
        data=[BushidoJobResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.get("/jobs/{job_id}", response_model=ApiResponse)
async def get_job(job_id: uuid.UUID, svc: BushidoJobService = Depends(get_bushido_job_service)):
    record = await svc.get_by_id(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return ApiResponse(data=BushidoJobResponse.model_validate(record))


@router.post("/run", response_model=ApiResponse, status_code=202)
async def trigger_run(
    body: BushidoRunRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger an immediate (manual) Bushido job run.

    Returns 202 Accepted immediately. The job runs in the background.
    Poll GET /jobs/{id} to track status.
    """
    from shogun.services.bushido_engine import run_job

    # Generate job ID upfront so we can return it to the caller
    job_id = uuid.uuid4()

    scope_dict = body.scope.model_dump()

    async def _run():
        await run_job(
            job_type=body.job_type.value,
            scope=scope_dict,
            trigger_mode=body.trigger_mode.value,
            priority=body.priority,
        )

    background_tasks.add_task(_run)

    return ApiResponse(
        data={
            "job_id": str(job_id),
            "job_type": body.job_type.value,
            "status": "queued",
            "message": "Job dispatched. Poll GET /api/v1/bushido/jobs for status.",
        }
    )


# ── Recommendations ──────────────────────────────────────────


@router.get("/recommendations", response_model=ApiResponse)
async def list_recommendations(
    svc: BushidoRecommendationService = Depends(get_bushido_recommendation_service),
):
    records, total = await svc.get_all()
    return ApiResponse(
        data=[BushidoRecommendationResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.post("/recommendations/{rec_id}/approve", response_model=ApiResponse)
async def approve_recommendation(
    rec_id: uuid.UUID,
    svc: BushidoRecommendationService = Depends(get_bushido_recommendation_service),
):
    record = await svc.update(rec_id, status="approved")
    if not record:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return ApiResponse(data=BushidoRecommendationResponse.model_validate(record))


@router.post("/recommendations/{rec_id}/reject", response_model=ApiResponse)
async def reject_recommendation(
    rec_id: uuid.UUID,
    svc: BushidoRecommendationService = Depends(get_bushido_recommendation_service),
):
    record = await svc.update(rec_id, status="rejected")
    if not record:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return ApiResponse(data=BushidoRecommendationResponse.model_validate(record))


# ── Schedules ────────────────────────────────────────────────


@router.get("/reminders", response_model=ApiResponse)
async def list_reminders(
    status: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    records = await ReminderService(db).list(status=status, user_id=user_id, tenant_id=tenant_id)
    return ApiResponse(
        data=[ReminderResponse.model_validate(record) for record in records],
        meta={"total": len(records)},
    )


@router.post("/reminders", response_model=ApiResponse, status_code=201)
async def create_reminder(body: ReminderCreate, db: AsyncSession = Depends(get_db)):
    # Public API entries are operator-owned; AI/system origins are reserved for internal tools.
    data = body.model_dump()
    data.update(origin="user", requires_confirmation=False)
    record = await ReminderService(db).create(**data)
    return ApiResponse(data=ReminderResponse.model_validate(record))


@router.post("/reminders/parse", response_model=ApiResponse)
async def parse_reminder(body: ReminderParseRequest):
    try:
        parsed = ReminderCreate.model_validate(parse_reminder_text(body.text, body.timezone))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse(data=parsed.model_dump(mode="json"))


@router.get("/reminders/{task_id}", response_model=ApiResponse)
async def get_reminder(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    record = await ReminderService(db).get(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return ApiResponse(data=ReminderResponse.model_validate(record))


@router.patch("/reminders/{task_id}", response_model=ApiResponse)
async def update_reminder(task_id: uuid.UUID, body: ReminderUpdate, db: AsyncSession = Depends(get_db)):
    record = await ReminderService(db).update(task_id, **body.model_dump(exclude_unset=True))
    if not record:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return ApiResponse(data=ReminderResponse.model_validate(record))


async def _reminder_action(task_id: uuid.UUID, action: str, db: AsyncSession, minutes: int | None = None):
    try:
        record = await ReminderService(db).transition(task_id, action, snooze_minutes=minutes)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not record:
        raise HTTPException(status_code=404, detail="Reminder not found")
    return ApiResponse(data=ReminderResponse.model_validate(record))


@router.post("/reminders/{task_id}/pause", response_model=ApiResponse)
async def pause_reminder(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _reminder_action(task_id, "pause", db)


@router.post("/reminders/{task_id}/resume", response_model=ApiResponse)
async def resume_reminder(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _reminder_action(task_id, "resume", db)


@router.post("/reminders/{task_id}/snooze", response_model=ApiResponse)
async def snooze_reminder(task_id: uuid.UUID, body: ReminderSnoozeRequest, db: AsyncSession = Depends(get_db)):
    return await _reminder_action(task_id, "snooze", db, body.minutes)


@router.post("/reminders/{task_id}/cancel", response_model=ApiResponse)
async def cancel_reminder(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _reminder_action(task_id, "cancel", db)


@router.post("/reminders/{task_id}/complete", response_model=ApiResponse)
async def complete_reminder(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _reminder_action(task_id, "complete", db)


@router.get("/reminders/{task_id}/runs", response_model=ApiResponse)
async def list_reminder_runs(task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    service = ReminderService(db)
    if not await service.get(task_id):
        raise HTTPException(status_code=404, detail="Reminder not found")
    records = await service.runs(task_id)
    return ApiResponse(
        data=[ReminderRunResponse.model_validate(record) for record in records],
        meta={"total": len(records)},
    )


@router.get("/schedules", response_model=ApiResponse)
async def list_schedules(
    svc: BushidoScheduleService = Depends(get_bushido_schedule_service),
):
    """List every cron-backed schedule, including scheduled AgentFlows."""
    records, total = await svc.get_all(limit=200)
    from sqlalchemy import select

    from shogun.db.models.agent_flow import AgentFlow
    from shogun.scheduler import scheduler_job_snapshot

    schedule_items = []
    for record in records:
        item = BushidoScheduleResponse.model_validate(record).model_dump(mode="json")
        runtime = scheduler_job_snapshot(f"bushido_{record.id}")
        if runtime["next_run_at"]:
            runtime["next_run_at"] = runtime["next_run_at"].isoformat()
        item.update(runtime)
        item["source"] = "bushido"
        schedule_items.append(item)

    flow_result = await svc.session.execute(
        select(
            AgentFlow.id,
            AgentFlow.name,
            AgentFlow.description,
            AgentFlow.status,
            AgentFlow.schedule_config,
            AgentFlow.created_at,
            AgentFlow.updated_at,
        )
        .where(
            AgentFlow.trigger_type == "scheduled",
            AgentFlow.is_deleted.is_(False),
        )
        .order_by(AgentFlow.created_at)
    )
    flows = list(flow_result.mappings().all())
    for flow in flows:
        config = flow["schedule_config"] or {}
        runtime = scheduler_job_snapshot(f"agentflow_{flow['id']}")
        next_run = runtime["next_run_at"]
        schedule_items.append({
            "id": str(flow["id"]),
            "flow_id": str(flow["id"]),
            "name": flow["name"],
            "job_type": "agent_flow",
            "frequency": config.get("frequency", "nightly"),
            "schedule_time": config.get("schedule_time", "02:00"),
            "schedule_days": config.get("schedule_days"),
            "schedule_day": config.get("schedule_day"),
            "minute_offset": config.get("minute_offset", 0),
            "schedule_datetime": None,
            "scope": {},
            "priority": 50,
            "all_agents": False,
            "dry_run": False,
            "auto_approve": False,
            "task_instruction": flow["description"],
            "is_enabled": flow["status"] == "active",
            "is_preset": False,
            "flow_status": flow["status"],
            "last_run_at": None,
            "next_run_at": next_run.isoformat() if next_run else None,
            "created_at": flow["created_at"].isoformat(),
            "updated_at": flow["updated_at"].isoformat(),
            "source": "agent_flow",
            "scheduler_job_id": runtime["scheduler_job_id"],
            "scheduler_registered": runtime["scheduler_registered"],
        })

    return ApiResponse(
        data=schedule_items,
        meta={
            "total": len(schedule_items),
            "bushido_schedules": total,
            "agent_flow_schedules": len(flows),
            "scheduler": "APScheduler",
        },
    )


@router.post("/schedules", response_model=ApiResponse, status_code=201)
async def create_schedule(
    body: BushidoScheduleCreate,
    svc: BushidoScheduleService = Depends(get_bushido_schedule_service),
):
    """Create a new custom Bushido schedule and register it with APScheduler."""
    data = body.model_dump()
    # Normalise scope dict
    if hasattr(data.get("scope"), "model_dump"):
        data["scope"] = data["scope"].model_dump()

    record = await svc.create(**data)

    # Register with APScheduler
    from shogun.scheduler import register_schedule
    try:
        await register_schedule(record)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Schedule could not be registered: {exc}",
        ) from exc

    return ApiResponse(
        data=BushidoScheduleResponse.model_validate(record),
        meta={"scheduler_registered": True, "scheduler_job_id": f"bushido_{record.id}"},
    )


@router.get("/schedules/{schedule_id}", response_model=ApiResponse)
async def get_schedule(
    schedule_id: uuid.UUID,
    svc: BushidoScheduleService = Depends(get_bushido_schedule_service),
):
    record = await svc.get_by_id(schedule_id)
    if not record:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ApiResponse(data=BushidoScheduleResponse.model_validate(record))


@router.put("/schedules/{schedule_id}", response_model=ApiResponse)
async def update_schedule(
    schedule_id: uuid.UUID,
    body: BushidoScheduleUpdate,
    svc: BushidoScheduleService = Depends(get_bushido_schedule_service),
):
    """Update a schedule definition and re-register with APScheduler."""
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    record = await svc.update(schedule_id, **update_data)
    if not record:
        raise HTTPException(status_code=404, detail="Schedule not found")

    from shogun.scheduler import register_schedule
    try:
        await register_schedule(record)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Schedule could not be re-registered: {exc}",
        ) from exc

    return ApiResponse(data=BushidoScheduleResponse.model_validate(record))


@router.patch("/schedules/{schedule_id}/toggle", response_model=ApiResponse)
async def toggle_schedule(
    schedule_id: uuid.UUID,
    svc: BushidoScheduleService = Depends(get_bushido_schedule_service),
):
    """Enable or disable a schedule. Registers/deregisters from APScheduler accordingly."""
    record = await svc.get_by_id(schedule_id)
    if not record:
        raise HTTPException(status_code=404, detail="Schedule not found")

    new_enabled = not record.is_enabled
    record = await svc.update(schedule_id, is_enabled=new_enabled)

    from shogun.scheduler import deregister_schedule, register_schedule
    try:
        if new_enabled:
            await register_schedule(record)
        else:
            await deregister_schedule(schedule_id)
            record.next_run_at = None
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Schedule state could not be changed: {exc}",
        ) from exc

    return ApiResponse(
        data=BushidoScheduleResponse.model_validate(record),
        meta={"is_enabled": new_enabled},
    )


@router.patch("/schedules/preset/{job_type}/toggle", response_model=ApiResponse)
async def toggle_preset_schedule(
    job_type: str,
    svc: BushidoScheduleService = Depends(get_bushido_schedule_service),
):
    """Toggle a preset schedule on/off by job_type string."""
    record = await svc.get_by_job_type(job_type)
    if not record:
        raise HTTPException(status_code=404, detail=f"No preset schedule found for job_type={job_type!r}")

    new_enabled = not record.is_enabled
    record = await svc.update(record.id, is_enabled=new_enabled)

    from shogun.scheduler import deregister_schedule, register_schedule
    try:
        if new_enabled:
            await register_schedule(record)
        else:
            await deregister_schedule(record.id)
            record.next_run_at = None
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Preset schedule state could not be changed: {exc}",
        ) from exc

    return ApiResponse(
        data=BushidoScheduleResponse.model_validate(record),
        meta={"is_enabled": new_enabled},
    )


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    schedule_id: uuid.UUID,
    svc: BushidoScheduleService = Depends(get_bushido_schedule_service),
):
    """Delete a custom schedule (presets cannot be deleted, only disabled)."""
    record = await svc.get_by_id(schedule_id)
    if not record:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if record.is_preset:
        raise HTTPException(
            status_code=400,
            detail="Preset schedules cannot be deleted. Use toggle to disable them.",
        )

    # Deregister from APScheduler first
    try:
        from shogun.scheduler import deregister_schedule
        await deregister_schedule(schedule_id)
    except Exception:
        pass

    await svc.delete(schedule_id)
    return Response(status_code=204)


# ── Legacy endpoint (kept for backward compat) ────────────────


@router.put("/schedule", response_model=ApiResponse)
async def update_schedule_legacy(
    body: BushidoScheduleUpdate,
    svc: AgentService = Depends(get_agent_service),
):
    """Update the Bushido schedule flags for the primary Shogun (legacy flat format)."""
    from shogun.db.models.agent import Agent
    filters = [Agent.agent_type == "shogun", Agent.is_primary == True]
    records, _ = await svc.get_all(filters=filters)

    if not records:
        raise HTTPException(status_code=404, detail="Primary Shogun agent not found")

    shogun = records[0]
    updated = await svc.update(shogun.id, bushido_settings=body.model_dump())
    return ApiResponse(data=updated.bushido_settings)
