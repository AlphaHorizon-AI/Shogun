"""Skill routes — CRUD, import, install for the Dojo."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db, get_skill_service, get_skill_source_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.skills import (
    ActiveSkillRunResponse,
    SkillActivationRequest,
    SkillActivationResponse,
    SkillOutcomeRequest,
    SkillResponse,
    SkillSourceCreate,
    SkillSourceResponse,
)
from shogun.services.active_skill_service import SkillActivationService, SkillEmbeddingService
from shogun.services.event_logger import EventLogger
from shogun.services.skill_service import SkillService, SkillSourceService

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.get("/sources", response_model=ApiResponse)
async def list_sources(svc: SkillSourceService = Depends(get_skill_source_service)):
    records, total = await svc.get_all()
    return ApiResponse(
        data=[SkillSourceResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.post("/sources", response_model=ApiResponse, status_code=201)
async def add_source(
    body: SkillSourceCreate,
    svc: SkillSourceService = Depends(get_skill_source_service),
):
    record = await svc.create(**body.model_dump())
    return ApiResponse(data=SkillSourceResponse.model_validate(record))


@router.get("", response_model=ApiResponse)
async def list_skills(
    source_id: uuid.UUID | None = None,
    status: str | None = None,
    search: str | None = None,
    svc: SkillService = Depends(get_skill_service),
):
    from shogun.db.models.skill import Skill
    filters = [Skill.is_deleted == False]
    if source_id:
        filters.append(Skill.source_id == source_id)
    if status:
        filters.append(Skill.status == status)
    if search:
        filters.append(Skill.name.ilike(f"%{search.strip()}%"))

    records, total = await svc.get_all(filters=filters)
    return ApiResponse(
        data=[SkillResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.post("/activate", response_model=ApiResponse)
async def activate_skills(body: SkillActivationRequest, db: AsyncSession = Depends(get_db)):
    service = SkillActivationService(db)
    result = await service.activate(body)
    await db.commit()
    return ApiResponse(data=SkillActivationResponse.model_validate(result))


@router.post("/outcome", response_model=ApiResponse)
async def report_skill_outcome(body: SkillOutcomeRequest, db: AsyncSession = Depends(get_db)):
    service = SkillActivationService(db)
    try:
        record = await service.outcome(body.active_skill_run_id, body.outcome, body.outcome_summary)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.commit()
    return ApiResponse(data={"id": str(record.id), "outcome": record.outcome})


@router.get("/active-runs", response_model=ApiResponse)
async def list_active_skill_runs(
    run_id: str | None = None,
    stack_run_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    from shogun.db.models.active_skill_run import ActiveSkillRun
    from shogun.db.models.skill import Skill

    query = (
        select(ActiveSkillRun, Skill.name)
        .join(Skill, Skill.id == ActiveSkillRun.skill_id)
        .order_by(ActiveSkillRun.created_at.desc())
        .limit(limit)
    )
    if run_id:
        query = query.where(ActiveSkillRun.run_id == run_id)
    if stack_run_id:
        query = query.where(ActiveSkillRun.stack_run_id == stack_run_id)
    rows = (await db.execute(query)).all()
    data = []
    for record, skill_name in rows:
        payload = ActiveSkillRunResponse.model_validate(record).model_dump()
        payload["skill_name"] = skill_name
        data.append(payload)
    return ApiResponse(data=data, meta={"total": len(data)})


async def _set_skill_status(skill_id: uuid.UUID, status: str, db: AsyncSession):
    from shogun.db.models.skill import Skill

    skill = await db.get(Skill, skill_id)
    if not skill or skill.is_deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    skill.status = status
    await EventLogger.emit(
        category="skill", event_type=f"skill.{status}",
        action=f"Skill '{skill.name}' {status}", detail={"skill_id": str(skill.id)}, db_session=db,
    )
    await db.commit()
    return ApiResponse(data=SkillResponse.model_validate(skill))


@router.post("/{skill_id}/enable", response_model=ApiResponse)
async def enable_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _set_skill_status(skill_id, "installed", db)


@router.post("/{skill_id}/disable", response_model=ApiResponse)
async def disable_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    return await _set_skill_status(skill_id, "disabled", db)


@router.post("/{skill_id}/rebuild-brief", response_model=ApiResponse)
async def rebuild_skill_brief(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from shogun.db.models.skill import Skill

    skill = await db.get(Skill, skill_id)
    if not skill or skill.is_deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    brief = await SkillActivationService(db).rebuild_brief(skill)
    await db.commit()
    return ApiResponse(data={"skill_id": str(skill.id), "brief": brief})


@router.post("/{skill_id}/reindex", response_model=ApiResponse)
async def reindex_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from shogun.db.models.skill import Skill

    skill = await db.get(Skill, skill_id)
    if not skill or skill.is_deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    try:
        embedding_id = await SkillEmbeddingService.index(skill)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Skill index unavailable: {exc}") from exc
    await EventLogger.emit(
        category="skill", event_type="skill.indexed", action=f"Skill '{skill.name}' indexed",
        detail={"skill_id": str(skill.id), "embedding_id": embedding_id}, db_session=db,
    )
    await db.commit()
    return ApiResponse(data={"skill_id": str(skill.id), "embedding_id": embedding_id})


@router.get("/{skill_id}", response_model=ApiResponse)
async def get_skill(skill_id: uuid.UUID, svc: SkillService = Depends(get_skill_service)):
    record = await svc.get_by_id(skill_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    return ApiResponse(data=SkillResponse.model_validate(record))
