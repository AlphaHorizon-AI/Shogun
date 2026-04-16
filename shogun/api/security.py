"""Security routes — policies, assignments, simulation."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_security_service, get_db
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

# ── In-process posture store (persisted via Agent.bushido_settings) ──
_POSTURE_KEY = "security_posture"
_DEFAULT_POSTURE = {
    "active_tier": "tactical",
    "filesystem_mode": "scoped",
    "network_mode": "allowlist",
    "shell_enabled": False,
    "skill_auto_install": False,
    "max_active_subagents": 5,
    "kill_switch_enabled": True,
    "kill_switch_active": False,   # True when the kill switch has been triggered
}


async def _get_agent_posture() -> dict:
    """Read security posture from primary Shogun agent's bushido_settings."""
    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent
    from sqlalchemy import select

    async with async_session_factory() as db:
        result = await db.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            ).limit(1)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return dict(_DEFAULT_POSTURE)
        bushido = agent.bushido_settings or {}
        stored = bushido.get(_POSTURE_KEY, {})
        return {**_DEFAULT_POSTURE, **stored}


async def _save_agent_posture(posture: dict) -> None:
    """Persist security posture into primary Shogun agent's bushido_settings."""
    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent
    from sqlalchemy import select
    import json

    async with async_session_factory() as db:
        result = await db.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            ).limit(1)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return
        bushido = dict(agent.bushido_settings or {})
        bushido[_POSTURE_KEY] = posture
        agent.bushido_settings = bushido
        await db.commit()


# ── Posture endpoints ────────────────────────────────────────────────

@router.get("/posture", response_model=ApiResponse)
async def get_security_posture():
    posture = await _get_agent_posture()
    return ApiResponse(data=SecurityPostureResponse(**posture).model_dump())


@router.patch("/posture", response_model=ApiResponse)
async def update_security_posture(body: dict):
    """Update security posture fields. Persisted across restarts."""
    current = await _get_agent_posture()
    allowed_fields = set(_DEFAULT_POSTURE.keys())
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    current.update(updates)
    await _save_agent_posture(current)
    return ApiResponse(data=SecurityPostureResponse(**current).model_dump())


# ── Policy endpoints ─────────────────────────────────────────────────

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


@router.delete("/policies/{policy_id}", response_model=ApiResponse)
async def delete_policy(
    policy_id: uuid.UUID,
    svc: SecurityService = Depends(get_security_service),
):
    record = await svc.get_by_id(policy_id)
    if not record:
        raise HTTPException(status_code=404, detail="Policy not found")
    if record.is_builtin:
        raise HTTPException(status_code=403, detail="Cannot delete built-in policies")
    await svc.delete(policy_id)
    return ApiResponse(data={"deleted": str(policy_id)})


@router.post("/simulate", response_model=ApiResponse)
async def simulate_permissions(body: PermissionSimulateRequest):
    return ApiResponse(
        data=PermissionSimulateResponse(allowed=True, warnings=["Simulation not yet implemented"], denials=[]).model_dump()
    )


@router.post("/kill-switch", response_model=ApiResponse)
async def activate_kill_switch():
    """Activate global kill switch — sets posture to shrine and disables shell. Persisted."""
    posture = await _get_agent_posture()
    posture["active_tier"] = "shrine"
    posture["shell_enabled"] = False
    posture["skill_auto_install"] = False
    posture["kill_switch_active"] = True
    await _save_agent_posture(posture)
    return ApiResponse(data={**posture, "message": "All agent activity suspended. Posture set to SHRINE."})


@router.delete("/kill-switch", response_model=ApiResponse)
async def reset_kill_switch():
    """Deactivate kill switch and restore tactical posture."""
    posture = await _get_agent_posture()
    posture["active_tier"] = "tactical"
    posture["shell_enabled"] = False
    posture["kill_switch_active"] = False
    await _save_agent_posture(posture)
    return ApiResponse(data={**posture, "message": "Kill switch reset. Posture restored to TACTICAL."})
