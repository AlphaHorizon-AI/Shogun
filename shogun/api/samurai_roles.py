"""Samurai Role routes — CRUD for functional templates."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_samurai_role_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.samurai_roles import (
    SamuraiRoleCreate,
    SamuraiRoleResponse,
    SamuraiRoleUpdate,
)
from shogun.services.samurai_role_service import SamuraiRoleService

router = APIRouter(prefix="/samurai-roles", tags=["Samurai Roles"])


@router.get("", response_model=ApiResponse)
async def list_samurai_roles(
    builtin_only: bool = False,
    active_only: bool = True,
    svc: SamuraiRoleService = Depends(get_samurai_role_service),
):
    filters = []
    from shogun.db.models.samurai_role import SamuraiRole

    if builtin_only:
        filters.append(SamuraiRole.is_builtin == True)
    if active_only:
        filters.append(SamuraiRole.is_active == True)

    print(f"DEBUG: list_samurai_roles - Builtin Only: {builtin_only}, Active Only: {active_only}")
    records, total = await svc.get_all(filters=filters)
    print(f"DEBUG: list_samurai_roles - Records Foud: {len(records)}, Total: {total}")
    
    data = [SamuraiRoleResponse.model_validate(r) for r in records]
    print(f"DEBUG: list_samurai_roles - Validated {len(data)} records")
    
    return ApiResponse(
        data=data,
        meta={"total": total},
    )


@router.get("/{role_id}", response_model=ApiResponse)
async def get_samurai_role(
    role_id: uuid.UUID,
    svc: SamuraiRoleService = Depends(get_samurai_role_service),
):
    record = await svc.get_by_id(role_id)
    if not record:
        raise HTTPException(status_code=404, detail="Samurai Role not found")
    return ApiResponse(data=SamuraiRoleResponse.model_validate(record))


@router.post("", response_model=ApiResponse, status_code=201)
async def create_samurai_role(
    body: SamuraiRoleCreate,
    svc: SamuraiRoleService = Depends(get_samurai_role_service),
):
    record = await svc.create(**body.model_dump())
    return ApiResponse(data=SamuraiRoleResponse.model_validate(record))


@router.patch("/{role_id}", response_model=ApiResponse)
async def update_samurai_role(
    role_id: uuid.UUID,
    body: SamuraiRoleUpdate,
    svc: SamuraiRoleService = Depends(get_samurai_role_service),
):
    record = await svc.update(role_id, **body.model_dump(exclude_unset=True))
    if not record:
        raise HTTPException(status_code=404, detail="Samurai Role not found")
    return ApiResponse(data=SamuraiRoleResponse.model_validate(record))


@router.delete("/{role_id}", response_model=ApiResponse)
async def delete_samurai_role(
    role_id: uuid.UUID,
    svc: SamuraiRoleService = Depends(get_samurai_role_service),
):
    deleted = await svc.delete(role_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Samurai Role not found")
    return ApiResponse(data={"deleted": True})
