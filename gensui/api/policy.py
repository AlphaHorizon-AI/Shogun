"""Policy API — posture assignment, global posture control, effective posture resolution."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.api.deps import get_db, get_current_admin, require_role, get_shogun_identity
from gensui.services.posture_service import PostureService
from gensui.services.audit_service import AuditService

router = APIRouter(prefix="/policy", tags=["policy"])


class AssignPostureRequest(BaseModel):
    target_id: str
    target_type: str  # "member" | "group"
    posture_id: str


class GlobalPostureRequest(BaseModel):
    posture_id: str
    reason: str | None = None


@router.get("/effective/{shogun_id}")
async def get_effective_posture(
    shogun_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    identity: dict = Depends(get_shogun_identity),
):
    """Get the effective posture for a Shogun instance (used by Shogun client for policy sync)."""
    if str(shogun_id) != identity["shogun_id"]:
        raise HTTPException(status_code=403, detail="Cannot access another Shogun's policy")
    svc = PostureService(db)
    result = await svc.get_effective_posture_with_explanation(shogun_id)
    return result


@router.post("/assign")
async def assign_posture(
    req: AssignPostureRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin", "security_operator")),
):
    """Assign a posture to a member or group."""
    svc = PostureService(db)

    if req.target_type == "member":
        result = await svc.assign_to_member(uuid.UUID(req.target_id), uuid.UUID(req.posture_id))
    elif req.target_type == "group":
        result = await svc.assign_to_group(uuid.UUID(req.target_id), uuid.UUID(req.posture_id))
    else:
        raise HTTPException(status_code=400, detail="target_type must be 'member' or 'group'")

    if result is None:
        raise HTTPException(status_code=404, detail="Target not found")

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="policy.assign",
        actor_id=admin["id"], target_type=req.target_type, target_id=req.target_id,
        metadata_json={"posture_id": req.posture_id},
    )
    return {"status": "assigned", "target_type": req.target_type, "target_id": req.target_id}


@router.post("/global")
async def set_global_posture(
    req: GlobalPostureRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner")),
):
    """Activate a global posture override across ALL member Shoguns."""
    svc = PostureService(db)
    state = await svc.set_global_posture(
        posture_id=uuid.UUID(req.posture_id),
        activated_by=admin["id"],
        reason=req.reason,
    )

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="policy.global_activated",
        actor_id=admin["id"], target_type="global",
        metadata_json={"posture_id": req.posture_id, "posture_name": state.posture_name, "reason": req.reason},
    )
    return {
        "status": "global_posture_active",
        "posture_name": state.posture_name,
        "activated_by": state.activated_by,
    }


@router.post("/global/clear")
async def clear_global_posture(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner")),
):
    """Deactivate the global posture override."""
    svc = PostureService(db)
    state = await svc.clear_global_posture()

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="policy.global_cleared",
        actor_id=admin["id"], target_type="global",
    )
    return {"status": "global_posture_cleared"}


@router.get("/global")
async def get_global_posture(db: AsyncSession = Depends(get_db)):
    """Get the current global posture state."""
    svc = PostureService(db)
    state = await svc.get_global_state()
    if state is None:
        return {"is_active": False}
    return {
        "is_active": state.is_active,
        "posture_id": str(state.posture_id) if state.posture_id else None,
        "posture_name": state.posture_name,
        "activated_by": state.activated_by,
        "activated_at": state.activated_at.isoformat() if state.activated_at else None,
        "reason": state.reason,
    }
