"""Enterprise Identity API — service accounts, API keys, and SSO/OIDC management."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.api.deps import get_db, require_role
from gensui.services.audit_service import AuditService
from gensui.services.identity_service import IdentityService

router = APIRouter(prefix="/identity", tags=["identity"])


# ── Service Account Models ───────────────────────────────────

class CreateServiceAccountRequest(BaseModel):
    name: str
    description: str | None = None
    role: str = "readonly"
    scopes: dict | None = None
    rate_limit_rpm: int = 60
    expires_at: str | None = None  # ISO format


class UpdateServiceAccountRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    role: str | None = None
    scopes: dict | None = None
    rate_limit_rpm: int | None = None
    is_active: bool | None = None


# ── SSO Provider Models ─────────────────────────────────────

class CreateSSOProviderRequest(BaseModel):
    name: str
    provider_type: str = "oidc"
    issuer_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    discovery_url: str | None = None
    scopes: str = "openid profile email"
    audience: str | None = None
    claim_mapping: dict | None = None
    default_role: str = "readonly"
    role_mapping: dict | None = None
    auto_create_users: bool = False
    auto_activate_users: bool = False
    allowed_domains: str | None = None
    is_primary: bool = False


class UpdateSSOProviderRequest(BaseModel):
    name: str | None = None
    issuer_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scopes: str | None = None
    audience: str | None = None
    claim_mapping: dict | None = None
    default_role: str | None = None
    role_mapping: dict | None = None
    auto_create_users: bool | None = None
    auto_activate_users: bool | None = None
    allowed_domains: str | None = None
    is_active: bool | None = None
    is_primary: bool | None = None


# ── Service Account Endpoints ────────────────────────────────

def _sa_to_dict(sa) -> dict:
    """Serialize a ServiceAccount (never expose the hash)."""
    return {
        "id": str(sa.id),
        "name": sa.name,
        "description": sa.description,
        "api_key_prefix": sa.api_key_prefix,
        "role": sa.role,
        "scopes": sa.scopes_json,
        "rate_limit_rpm": sa.rate_limit_rpm,
        "is_active": sa.is_active,
        "expires_at": sa.expires_at.isoformat() if sa.expires_at else None,
        "last_used_at": sa.last_used_at.isoformat() if sa.last_used_at else None,
        "last_used_ip": sa.last_used_ip,
        "usage_count": sa.usage_count,
        "created_by": sa.created_by,
        "created_at": sa.created_at.isoformat() if sa.created_at else None,
        "authentication_available": False,
        "configuration_only": True,
    }


@router.get("/service-accounts")
async def list_service_accounts(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """List all service accounts."""
    svc = IdentityService(db)
    accounts = await svc.list_service_accounts()
    return {"accounts": [_sa_to_dict(sa) for sa in accounts]}


@router.post("/service-accounts")
async def create_service_account(
    req: CreateServiceAccountRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Create a service account. Returns the API key ONCE."""
    svc = IdentityService(db)
    expires = datetime.fromisoformat(req.expires_at) if req.expires_at else None

    sa, raw_key = await svc.create_service_account(
        name=req.name,
        description=req.description,
        role=req.role,
        scopes=req.scopes,
        rate_limit_rpm=req.rate_limit_rpm,
        expires_at=expires,
        created_by=admin["email"],
    )

    # Audit
    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="identity.service_account.created",
        actor_id=admin["id"], target_type="service_account", target_id=str(sa.id),
        metadata_json={"name": req.name, "role": req.role},
    )
    await db.commit()

    return {
        "account": _sa_to_dict(sa),
        "api_key": raw_key,
        "warning": (
            "This reserved credential is shown once, but no Gensui API endpoint "
            "accepts service-account keys in this release."
        ),
    }


@router.put("/service-accounts/{sa_id}")
async def update_service_account(
    sa_id: str,
    req: UpdateServiceAccountRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Update a service account."""
    svc = IdentityService(db)
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "scopes" in updates:
        updates["scopes_json"] = updates.pop("scopes")

    sa = await svc.update_service_account(uuid.UUID(sa_id), **updates)
    if sa is None:
        raise HTTPException(status_code=404, detail="Service account not found")

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="identity.service_account.updated",
        actor_id=admin["id"], target_type="service_account", target_id=sa_id,
    )
    await db.commit()
    return {"account": _sa_to_dict(sa)}


@router.post("/service-accounts/{sa_id}/revoke")
async def revoke_service_account(
    sa_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Revoke a service account (deactivate its API key)."""
    svc = IdentityService(db)
    success = await svc.revoke_service_account(uuid.UUID(sa_id))
    if not success:
        raise HTTPException(status_code=404, detail="Service account not found")

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="identity.service_account.revoked",
        actor_id=admin["id"], target_type="service_account", target_id=sa_id,
    )
    await db.commit()
    return {"status": "revoked"}


@router.post("/service-accounts/{sa_id}/rotate")
async def rotate_api_key(
    sa_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """Rotate the API key for a service account. Returns new key ONCE."""
    svc = IdentityService(db)
    result = await svc.rotate_api_key(uuid.UUID(sa_id))
    if result is None:
        raise HTTPException(status_code=404, detail="Service account not found")

    sa, raw_key = result
    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="identity.api_key.rotated",
        actor_id=admin["id"], target_type="service_account", target_id=sa_id,
    )
    await db.commit()

    return {
        "account": _sa_to_dict(sa),
        "api_key": raw_key,
        "warning": (
            "This reserved credential is shown once, but no Gensui API endpoint "
            "accepts service-account keys in this release."
        ),
    }


# ── SSO Provider Endpoints ──────────────────────────────────

def _sso_to_dict(p) -> dict:
    """Serialize an SSOProvider (never expose the client secret)."""
    return {
        "id": str(p.id),
        "name": p.name,
        "provider_type": p.provider_type,
        "issuer_url": p.issuer_url,
        "client_id": p.client_id,
        "has_client_secret": bool(p.client_secret_encrypted),
        "discovery_url": p.discovery_url,
        "scopes": p.scopes,
        "audience": p.audience,
        "claim_mapping": p.claim_mapping_json,
        "default_role": p.default_role,
        "role_mapping": p.role_mapping_json,
        "auto_create_users": p.auto_create_users,
        "auto_activate_users": p.auto_activate_users,
        "allowed_domains": p.allowed_domains,
        "is_active": p.is_active,
        "is_primary": p.is_primary,
        "created_by": p.created_by,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "authentication_available": False,
        "configuration_only": True,
    }


@router.get("/sso-providers")
async def list_sso_providers(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner", "admin")),
):
    """List all SSO/OIDC providers."""
    svc = IdentityService(db)
    providers = await svc.list_sso_providers()
    return {"providers": [_sso_to_dict(p) for p in providers]}


@router.post("/sso-providers")
async def create_sso_provider(
    req: CreateSSOProviderRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner")),
):
    """Store an inactive provider configuration for future implementation."""
    svc = IdentityService(db)
    provider = await svc.create_sso_provider(
        name=req.name,
        provider_type=req.provider_type,
        issuer_url=req.issuer_url,
        client_id=req.client_id,
        client_secret=req.client_secret,
        discovery_url=req.discovery_url,
        scopes=req.scopes,
        audience=req.audience,
        claim_mapping=req.claim_mapping,
        default_role=req.default_role,
        role_mapping=req.role_mapping,
        auto_create_users=req.auto_create_users,
        auto_activate_users=req.auto_activate_users,
        allowed_domains=req.allowed_domains,
        is_primary=req.is_primary,
        created_by=admin["email"],
    )

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="identity.sso_provider.created",
        actor_id=admin["id"], target_type="sso_provider", target_id=str(provider.id),
        metadata_json={"name": req.name, "type": req.provider_type},
    )
    await db.commit()

    return {"provider": _sso_to_dict(provider)}


@router.put("/sso-providers/{provider_id}")
async def update_sso_provider(
    provider_id: str,
    req: UpdateSSOProviderRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner")),
):
    """Update an SSO/OIDC provider."""
    svc = IdentityService(db)
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "claim_mapping" in updates:
        updates["claim_mapping_json"] = updates.pop("claim_mapping")
    if "role_mapping" in updates:
        updates["role_mapping_json"] = updates.pop("role_mapping")

    provider = await svc.update_sso_provider(uuid.UUID(provider_id), **updates)
    if provider is None:
        raise HTTPException(status_code=404, detail="SSO provider not found")

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="identity.sso_provider.updated",
        actor_id=admin["id"], target_type="sso_provider", target_id=provider_id,
    )
    await db.commit()

    return {"provider": _sso_to_dict(provider)}


@router.delete("/sso-providers/{provider_id}")
async def delete_sso_provider(
    provider_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_role("owner")),
):
    """Delete an SSO/OIDC provider."""
    svc = IdentityService(db)
    success = await svc.delete_sso_provider(uuid.UUID(provider_id))
    if not success:
        raise HTTPException(status_code=404, detail="SSO provider not found")

    audit = AuditService(db)
    await audit.append(
        actor_type="admin", action="identity.sso_provider.deleted",
        actor_id=admin["id"], target_type="sso_provider", target_id=provider_id,
    )
    await db.commit()

    return {"status": "deleted"}


# ── SSO Status & Configuration ──────────────────────────────

@router.get("/sso-status")
async def sso_status(
    db: AsyncSession = Depends(get_db),
):
    """Report SSO unavailable until a signed-token verifier is implemented."""
    return {
        "sso_enabled": False,
        "authentication_available": False,
        "reason": "Signed OIDC validation and SSO login are not implemented in this release",
    }
