"""API dependencies — database sessions, auth guards, role enforcement."""

from __future__ import annotations

import hashlib
import hmac
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.db.engine import get_async_session
from gensui.services.auth_service import AuthService


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a database session."""
    async for session in get_async_session():
        yield session


async def get_current_admin(
    request: Request,
    authorization: str | None = Header(None),
    x_csrf_token: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate an API bearer token or the browser's HttpOnly access cookie."""
    bearer = (
        authorization.removeprefix("Bearer ").strip()
        if authorization and authorization.startswith("Bearer ")
        else None
    )
    token = bearer or request.cookies.get("gensui_access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    if not bearer and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        csrf_cookie = request.cookies.get("gensui_csrf_token")
        if not csrf_cookie or not x_csrf_token or not hmac.compare_digest(csrf_cookie, x_csrf_token):
            raise HTTPException(status_code=403, detail="CSRF validation failed")
    try:
        payload = AuthService.decode_token(token, expected_type="access")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    admin_id = payload.get("sub")
    if not admin_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    auth = AuthService(db)
    admin = await auth.get_by_id(uuid.UUID(admin_id))
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=401, detail="Admin account not found or inactive")

    return {
        "id": str(admin.id),
        "email": admin.email,
        "role": admin.role,
        "display_name": admin.display_name,
    }


def require_role(*allowed_roles: str):
    """Dependency factory that requires the admin to have one of the specified roles."""

    async def _check(admin: dict = Depends(get_current_admin)) -> dict:
        if admin["role"] not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{admin['role']}' is not authorized for this operation. "
                       f"Required: {', '.join(allowed_roles)}",
            )
        return admin

    return _check



# ── API Key Auth (Service Accounts) ──────────────────────────

SERVICE_ACCOUNT_AUTHENTICATION_AVAILABLE = False


async def get_api_key_identity(
    x_api_key: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    """Fail closed until service-account authentication is wired to API routes.

    Stored service-account records are configuration scaffolding. No Gensui API
    endpoint currently accepts them as authorization evidence.
    """
    if not x_api_key:
        return None

    if not SERVICE_ACCOUNT_AUTHENTICATION_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="Service-account API-key authentication is not available in this release",
        )

    from gensui.services.identity_service import IdentityService
    svc = IdentityService(db)
    sa = await svc.validate_api_key(x_api_key)

    if sa is None:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")

    return {
        "id": str(sa.id),
        "name": sa.name,
        "role": sa.role,
        "scopes": sa.scopes_json,
        "auth_type": "api_key",
    }


# ── Shogun Membership Auth ───────────────────────────────────

async def get_shogun_identity(
    x_shogun_id: str = Header(None),
    x_shogun_token: str = Header(None),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate a Shogun instance's identity from request headers."""
    if not x_shogun_id or not x_shogun_token:
        raise HTTPException(status_code=401, detail="Missing Shogun membership credentials")

    from gensui.services.member_service import MemberService
    svc = MemberService(db)

    try:
        member = await svc.get_by_id(uuid.UUID(x_shogun_id))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Shogun ID format")

    if member is None:
        raise HTTPException(status_code=401, detail="Unknown Shogun instance")

    if member.enrollment_status != "active":
        raise HTTPException(status_code=403, detail=f"Shogun enrollment status: {member.enrollment_status}")
    presented_hash = hashlib.sha256(x_shogun_token.encode("utf-8")).hexdigest()
    if not member.member_token_hash or not hmac.compare_digest(
        presented_hash, member.member_token_hash
    ):
        raise HTTPException(status_code=401, detail="Invalid Shogun membership credential")

    return {
        "shogun_id": str(member.id),
        "instance_name": member.instance_name,
        "enrollment_status": member.enrollment_status,
    }
