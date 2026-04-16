"""Bushido routes — reflection, maintenance, and self-improvement."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response

from shogun.api.deps import (
    get_agent_service,
    get_bushido_job_service,
    get_bushido_recommendation_service,
    get_bushido_schedule_service,
)
from shogun.schemas.bushido import (
    BushidoJobResponse,
    BushidoRecommendationResponse,
    BushidoRunRequest,
    BushidoScheduleCreate,
    BushidoScheduleResponse,
    BushidoScheduleUpdate,
)
from shogun.schemas.common import ApiResponse
from shogun.services.agent_service import AgentService
from shogun.services.bushido_service import (
    BushidoJobService,
    BushidoRecommendationService,
    BushidoScheduleService,
)

router = APIRouter(prefix="/bushido", tags=["Bushido"])

# ── Default calibration values ────────────────────────────────
DEFAULT_CALIBRATION = {
    "reflection_intensity": 70,
    "consolidation_rate": 45,
    "exploration_variance": 24,
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
    })


@router.put("/calibration", response_model=ApiResponse)
async def save_calibration(
    body: dict,
    agent_svc: AgentService = Depends(get_agent_service),
):
    """Save Bushido calibration settings to the Shogun's bushido_settings."""
    from shogun.db.models.agent import Agent
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

    await agent_svc.update(shogun.id, bushido_settings=current)

    return ApiResponse(data={
        "reflection_intensity": current["reflection_intensity"],
        "consolidation_rate": current["consolidation_rate"],
        "exploration_variance": current["exploration_variance"],
        "message": "Calibration saved.",
    })


@router.post("/calibration/reset", response_model=ApiResponse)
async def reset_calibration(
    agent_svc: AgentService = Depends(get_agent_service),
):
    """Reset Bushido calibration to baseline defaults."""
    from shogun.db.models.agent import Agent
    filters = [Agent.agent_type == "shogun", Agent.is_primary == True, Agent.is_deleted == False]
    records, _ = await agent_svc.get_all(filters=filters)

    if not records:
        raise HTTPException(status_code=404, detail="Primary Shogun agent not found")

    shogun = records[0]
    current = shogun.bushido_settings or {}
    current.update(DEFAULT_CALIBRATION)
    await agent_svc.update(shogun.id, bushido_settings=current)

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


@router.get("/schedules", response_model=ApiResponse)
async def list_schedules(
    svc: BushidoScheduleService = Depends(get_bushido_schedule_service),
):
    """List all Bushido schedules (presets + custom)."""
    records, total = await svc.get_all(limit=200)
    return ApiResponse(
        data=[BushidoScheduleResponse.model_validate(r) for r in records],
        meta={"total": total},
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
    try:
        from shogun.scheduler import register_schedule
        await register_schedule(record)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Scheduler registration failed: %s", exc)

    return ApiResponse(data=BushidoScheduleResponse.model_validate(record))


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

    try:
        from shogun.scheduler import register_schedule
        await register_schedule(record)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Scheduler re-registration failed: %s", exc)

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

    try:
        from shogun.scheduler import register_schedule, deregister_schedule
        if new_enabled:
            await register_schedule(record)
        else:
            await deregister_schedule(schedule_id)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Scheduler toggle failed: %s", exc)

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

    try:
        from shogun.scheduler import register_schedule, deregister_schedule
        if new_enabled:
            await register_schedule(record)
        else:
            await deregister_schedule(record.id)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Scheduler preset toggle failed: %s", exc)

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
