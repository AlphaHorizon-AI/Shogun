"""Mission routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_mission_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.missions import MissionCreate, MissionResponse
from shogun.services.mission_service import MissionService

router = APIRouter(prefix="/missions", tags=["Missions"])


@router.get("", response_model=ApiResponse)
async def list_missions(
    status: str | None = None,
    svc: MissionService = Depends(get_mission_service),
):
    filters = []
    if status:
        from shogun.db.models.mission import Mission
        filters.append(Mission.status == status)

    records, total = await svc.get_all(filters=filters)
    return ApiResponse(
        data=[MissionResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.get("/{mission_id}", response_model=ApiResponse)
async def get_mission(mission_id: uuid.UUID, svc: MissionService = Depends(get_mission_service)):
    record = await svc.get_by_id(mission_id)
    if not record:
        raise HTTPException(status_code=404, detail="Mission not found")
    return ApiResponse(data=MissionResponse.model_validate(record))


@router.post("", response_model=ApiResponse, status_code=201)
async def create_mission(
    body: MissionCreate,
    svc: MissionService = Depends(get_mission_service),
):
    record = await svc.create(**body.model_dump())
    return ApiResponse(data=MissionResponse.model_validate(record))


@router.post("/{mission_id}/cancel", response_model=ApiResponse)
async def cancel_mission(mission_id: uuid.UUID, svc: MissionService = Depends(get_mission_service)):
    record = await svc.cancel(mission_id)
    if not record:
        raise HTTPException(status_code=404, detail="Mission not found")
    return ApiResponse(data=MissionResponse.model_validate(record))
