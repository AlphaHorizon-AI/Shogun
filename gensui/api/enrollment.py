"""Enrollment API — Shogun instance registration."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.api.deps import get_db, get_current_admin, require_role
from gensui.services.member_service import MemberService
from gensui.services.audit_service import AuditService

router = APIRouter(prefix="/enrollment", tags=["enrollment"])


class EnrollRequest(BaseModel):
    token: str
    instance_name: str
    hostname: str | None = None
    environment: str = "development"
    organization: str | None = None
    owner: str | None = None
    version: str | None = None
    build_hash: str | None = None
    public_key: str | None = None
    local_os: str | None = None
    deployment_type: str | None = None
    metadata: dict | None = None


class CreateTokenRequest(BaseModel):
    label: str | None = None
    max_uses: int = 1


@router.post("/enroll")
async def enroll(req: EnrollRequest, db: AsyncSession = Depends(get_db)):
    """Enroll a Shogun instance using an enrollment token."""
    svc = MemberService(db)
    member = await svc.enroll(
        token_str=req.token,
        instance_name=req.instance_name,
        hostname=req.hostname,
        environment=req.environment,
        organization=req.organization,
        owner=req.owner,
        version=req.version,
        build_hash=req.build_hash,
        public_key=req.public_key,
        local_os=req.local_os,
        deployment_type=req.deployment_type,
        metadata=req.metadata,
    )
    if member is None:
        raise HTTPException(status_code=400, detail="Invalid, expired, or exhausted enrollment token")

    # Audit
    audit = AuditService(db)
    await audit.append(
        actor_type="shogun",
        action="enrollment.request",
        actor_id=str(member.id),
        target_type="shogun_member",
        target_id=str(member.id),
        metadata_json={"instance_name": req.instance_name, "status": member.enrollment_status},
    )

    return {
        "shogun_id": str(member.id),
        "member_token": member._issued_member_token,
        "instance_name": member.instance_name,
        "enrollment_status": member.enrollment_status,
        "message": "Enrollment successful" if member.enrollment_status == "active"
                   else "Enrollment pending admin approval",
    }


@router.post("/approve/{member_id}")
async def approve_enrollment(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Approve a pending enrollment."""
    svc = MemberService(db)
    member = await svc.approve(member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="enrollment.approved",
        actor_id=admin["id"], target_type="shogun_member", target_id=str(member_id),
    )
    return {"shogun_id": str(member.id), "enrollment_status": member.enrollment_status}


@router.post("/reject/{member_id}")
async def reject_enrollment(
    member_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Reject a pending enrollment."""
    svc = MemberService(db)
    member = await svc.reject(member_id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member not found")

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="enrollment.rejected",
        actor_id=admin["id"], target_type="shogun_member", target_id=str(member_id),
    )
    return {"shogun_id": str(member.id), "enrollment_status": member.enrollment_status}


@router.get("/pending")
async def list_pending(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """List pending enrollment requests."""
    svc = MemberService(db)
    members, total = await svc.list_members(enrollment_filter="pending")
    return {
        "members": [
            {
                "id": str(m.id),
                "instance_name": m.instance_name,
                "hostname": m.hostname,
                "environment": m.environment,
                "organization": m.organization,
                "version": m.version,
                "local_os": m.local_os,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in members
        ],
        "total": total,
    }


@router.post("/tokens")
async def create_token(
    req: CreateTokenRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Create a new enrollment token."""
    svc = MemberService(db)
    token = await svc.create_enrollment_token(
        label=req.label, max_uses=req.max_uses, created_by=admin["id"],
    )
    return {
        "token": token._issued_token,
        "label": token.label,
        "max_uses": token.max_uses,
        "id": str(token.id),
    }


@router.get("/tokens")
async def list_tokens(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """List all enrollment tokens."""
    svc = MemberService(db)
    tokens = await svc.list_tokens()
    return [
        {
            "id": str(t.id),
            "token": "********",
            "label": t.label,
            "max_uses": t.max_uses,
            "use_count": t.use_count,
            "is_revoked": t.is_revoked,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tokens
    ]


@router.post("/tokens/{token_id}/revoke")
async def revoke_token(
    token_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Revoke an enrollment token."""
    svc = MemberService(db)
    token = await svc.revoke_token(token_id)
    if token is None:
        raise HTTPException(status_code=404, detail="Token not found")

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="enrollment.token_revoked",
        actor_id=admin["id"], target_type="enrollment_token", target_id=str(token_id),
        metadata_json={"label": token.label},
    )
    return {"id": str(token.id), "is_revoked": True, "label": token.label}
