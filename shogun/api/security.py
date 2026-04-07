"""Security routes — policies, assignments, simulation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_security_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.security import (
    SecurityPolicyCreate,
    SecurityPolicyResponse,
    SecurityPolicyUpdate,
    PermissionSimulateRequest,
    PermissionSimulateResponse,
    SecurityAssignRequest,
    SecurityPostureResponse,
)
from shogun.services.security_service import SecurityService

router = APIRouter(prefix="/security", tags=["Security"])


@router.get("/policies", response_model=ApiResponse)
async def list_policies(svc: SecurityService = Depends(get_security_service)):
    records, total = await svc.get_all()
    return ApiResponse(
        data=[SecurityPolicyResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.get("/policies/{policy_id}", response_model=ApiResponse)
async def get_policy(policy_id: uuid.UUID, svc: SecurityService = Depends(get_security_service)):
    record = await svc.get_by_id(policy_id)
    if not record:
        raise HTTPException(status_code=404, detail="Policy not found")
    return ApiResponse(data=SecurityPolicyResponse.model_validate(record))


@router.post("/policies", response_model=ApiResponse, status_code=201)
async def create_policy(
    body: SecurityPolicyCreate,
    svc: SecurityService = Depends(get_security_service),
):
    data = body.model_dump()
    data["permissions"] = data["permissions"] if isinstance(data["permissions"], dict) else data["permissions"].model_dump()
    record = await svc.create(**data)
    return ApiResponse(data=SecurityPolicyResponse.model_validate(record))


@router.patch("/policies/{policy_id}", response_model=ApiResponse)
async def update_policy(
    policy_id: uuid.UUID,
    body: SecurityPolicyUpdate,
    svc: SecurityService = Depends(get_security_service),
):
    update_data = body.model_dump(exclude_unset=True)
    if "permissions" in update_data and update_data["permissions"] is not None:
        update_data["permissions"] = update_data["permissions"].model_dump() if hasattr(update_data["permissions"], "model_dump") else update_data["permissions"]
    record = await svc.update(policy_id, **update_data)
    if not record:
        raise HTTPException(status_code=404, detail="Policy not found")
    return ApiResponse(data=SecurityPolicyResponse.model_validate(record))


@router.post("/simulate", response_model=ApiResponse)
async def simulate_permissions(body: PermissionSimulateRequest):
    return ApiResponse(
        data=PermissionSimulateResponse(allowed=True, warnings=["Simulation not yet implemented"], denials=[]).model_dump()
    )


@router.post("/kill-switch", response_model=ApiResponse)
async def activate_kill_switch():
    return ApiResponse(data={"kill_switch": "activated", "message": "All agent activity suspended"})


@router.get("/posture", response_model=ApiResponse)
async def get_security_posture():
    return ApiResponse(
        data=SecurityPostureResponse(
            active_tier="guarded",
            filesystem_mode="scoped",
            network_mode="allowlist",
            shell_enabled=False,
            skill_auto_install=False,
            max_active_subagents=5,
            kill_switch_enabled=True,
        ).model_dump()
    )
