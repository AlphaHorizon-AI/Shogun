"""Bushido routes — reflection and self-improvement."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import (
    get_agent_service,
    get_bushido_job_service,
    get_bushido_recommendation_service,
)
from shogun.schemas.bushido import (
    BushidoJobResponse,
    BushidoRecommendationResponse,
    BushidoRunRequest,
    BushidoScheduleUpdate,
)
from shogun.schemas.common import ApiResponse
from shogun.services.agent_service import AgentService
from shogun.services.bushido_service import BushidoJobService, BushidoRecommendationService

router = APIRouter(prefix="/bushido", tags=["Bushido"])


@router.get("/jobs", response_model=ApiResponse)
async def list_jobs(svc: BushidoJobService = Depends(get_bushido_job_service)):
    records, total = await svc.get_all()
    return ApiResponse(
        data=[BushidoJobResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.post("/run", response_model=ApiResponse, status_code=201)
async def trigger_run(
    body: BushidoRunRequest,
    svc: BushidoJobService = Depends(get_bushido_job_service),
):
    data = body.model_dump()
    data["scope"] = data["scope"] if isinstance(data["scope"], dict) else data["scope"].model_dump() if hasattr(data["scope"], "model_dump") else data["scope"]
    data["started_at"] = datetime.now(timezone.utc)
    record = await svc.create(**data)
    return ApiResponse(data=BushidoJobResponse.model_validate(record))


@router.get("/jobs/{job_id}", response_model=ApiResponse)
async def get_job(job_id: uuid.UUID, svc: BushidoJobService = Depends(get_bushido_job_service)):
    record = await svc.get_by_id(job_id)
    if not record:
        raise HTTPException(status_code=404, detail="Job not found")
    return ApiResponse(data=BushidoJobResponse.model_validate(record))


@router.get("/recommendations", response_model=ApiResponse)
async def list_recommendations(svc: BushidoRecommendationService = Depends(get_bushido_recommendation_service)):
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


@router.put("/schedule", response_model=ApiResponse)
async def update_schedule(
    body: BushidoScheduleUpdate,
    svc: AgentService = Depends(get_agent_service),
):
    """Update the Bushido schedule for the primary Shogun."""
    # Find primary shogun
    from shogun.db.models.agent import Agent
    filters = [Agent.agent_type == "shogun", Agent.is_primary == True]
    records, _ = await svc.get_all(filters=filters)
    
    if not records:
        raise HTTPException(status_code=404, detail="Primary Shogun agent not found")
        
    shogun = records[0]
    updated = await svc.update(shogun.id, bushido_settings=body.model_dump())
    
    return ApiResponse(data=updated.bushido_settings)
