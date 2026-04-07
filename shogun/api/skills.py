"""Skill routes — CRUD, import, install for the Dojo."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_skill_service, get_skill_source_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.skills import SkillResponse, SkillSourceCreate, SkillSourceResponse
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

    records, total = await svc.get_all(filters=filters)
    return ApiResponse(
        data=[SkillResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.get("/{skill_id}", response_model=ApiResponse)
async def get_skill(skill_id: uuid.UUID, svc: SkillService = Depends(get_skill_service)):
    record = await svc.get_by_id(skill_id)
    if not record or record.is_deleted:
        raise HTTPException(status_code=404, detail="Skill not found")
    return ApiResponse(data=SkillResponse.model_validate(record))
