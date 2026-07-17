"""SkillOpt API router."""

import uuid
from typing import List, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.services.skillopt.versioning import SkillVersionService
from shogun.services.skillopt.optimizer import SkillOptService
from shogun.services.skillopt.promotion import SkillPromotionService
from shogun.services.skillopt.usage_tracking import SkillUsageTrackingService

router = APIRouter(prefix="/skillopt", tags=["skillopt"])

class TrainingRunRequest(BaseModel):
    skill_id: uuid.UUID
    optimizer_model: str = "high_capability"
    target_model_profile: str = "balanced"

class CandidatePromotionRequest(BaseModel):
    candidate_id: uuid.UUID

class CandidateRejectionRequest(BaseModel):
    candidate_id: uuid.UUID
    reason: str


@router.post("/runs")
async def start_training_run(request: TrainingRunRequest, db: AsyncSession = Depends(get_db)):
    """Start a new SkillOpt training run."""
    svc = SkillOptService(db)
    try:
        run = await svc.start_training_run(
            skill_id=request.skill_id,
            optimizer_model=request.optimizer_model,
            target_model_profile=request.target_model_profile
        )
        return {"id": run.id, "status": run.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/skills/{skill_id}/versions")
async def get_skill_versions(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get all versions for a skill."""
    svc = SkillVersionService(db)
    versions = await svc.get_versions(skill_id)
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "status": v.status,
            "created_at": v.created_at,
            "validation_score": v.validation_score
        }
        for v in versions
    ]

@router.post("/candidates/{candidate_id}/promote")
async def promote_candidate(candidate_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Promote a candidate to active version."""
    svc = SkillPromotionService(db)
    try:
        success = await svc.promote_candidate(candidate_id)
        if not success:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return {"status": "promoted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/candidates/{candidate_id}/reject")
async def reject_candidate(request: CandidateRejectionRequest, db: AsyncSession = Depends(get_db)):
    """Reject a candidate."""
    svc = SkillPromotionService(db)
    success = await svc.reject_candidate(request.candidate_id, request.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"status": "rejected"}

@router.get("/skills/{skill_id}/usage")
async def get_skill_usage(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get usage events for a skill."""
    svc = SkillUsageTrackingService(db)
    events = await svc.get_usage_for_skill(skill_id)
    return [
        {
            "id": e.id,
            "skill_version_id": e.skill_version_id,
            "outcome": e.outcome,
            "score": e.score,
            "created_at": e.created_at
        }
        for e in events
    ]
