"""Auth API — admin login and session management."""

from __future__ import annotations

import hmac
import secrets
import time
import uuid
from collections import deque

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.api.deps import get_current_admin, get_db
from gensui.config import gensui_settings
from gensui.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
_login_attempts: dict[str, deque[float]] = {}


def _check_login_rate(client: str) -> None:
    now = time.monotonic()
    attempts = _login_attempts.get(client)
    if attempts is None:
        if len(_login_attempts) >= 10_000:
            raise HTTPException(status_code=429, detail="Login rate limit capacity exceeded")
        attempts = deque()
        _login_attempts[client] = attempts
    while attempts and attempts[0] <= now - 60:
        attempts.popleft()
    if len(attempts) >= 5:
        raise HTTPException(status_code=429, detail="Too many login attempts")
    attempts.append(now)


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    admin: dict


class AdminProfile(BaseModel):
    id: str
    email: str
    role: str
    display_name: str


def _admin_payload(admin) -> dict:
    return {
        "id": str(admin.id),
        "email": admin.email,
        "role": admin.role,
        "display_name": admin.display_name,
    }


def _issue_browser_session(response: Response, admin) -> str:
    access = AuthService.create_access_token(str(admin.id), admin.email, admin.role)
    refresh = AuthService.create_refresh_token(str(admin.id), admin.email, admin.role)
    csrf = secrets.token_urlsafe(32)
    common = {
        "secure": gensui_settings.gensui_cookie_secure,
        "samesite": "strict",
        "path": "/",
    }
    response.set_cookie(
        "gensui_access_token",
        access,
        httponly=True,
        max_age=gensui_settings.gensui_access_token_minutes * 60,
        **common,
    )
    response.set_cookie(
        "gensui_refresh_token",
        refresh,
        httponly=True,
        max_age=gensui_settings.gensui_refresh_token_days * 86_400,
        **common,
    )
    response.set_cookie(
        "gensui_csrf_token",
        csrf,
        httponly=False,
        max_age=gensui_settings.gensui_refresh_token_days * 86_400,
        **common,
    )
    return access


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate an admin user and return a JWT token."""
    client = request.client.host if request.client else "unknown"
    _check_login_rate(client)
    auth = AuthService(db)
    admin = await auth.authenticate(req.email, req.password)
    if admin is None:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _issue_browser_session(response, admin)
    _login_attempts.pop(client, None)

    return LoginResponse(
        token=token,
        admin=_admin_payload(admin),
    )


@router.post("/refresh", response_model=LoginResponse)
async def refresh_session(
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
):
    csrf_cookie = request.cookies.get("gensui_csrf_token")
    if not csrf_cookie or not x_csrf_token or not hmac.compare_digest(csrf_cookie, x_csrf_token):
        raise HTTPException(status_code=403, detail="CSRF validation failed")
    refresh_token = request.cookies.get("gensui_refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")
    try:
        payload = AuthService.decode_token(refresh_token, expected_type="refresh")
        admin_id = uuid.UUID(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token") from exc
    admin = await AuthService(db).get_by_id(admin_id)
    if admin is None or not admin.is_active:
        raise HTTPException(status_code=401, detail="Admin account not found or inactive")
    access = _issue_browser_session(response, admin)
    return LoginResponse(token=access, admin=_admin_payload(admin))


@router.post("/logout")
async def logout(response: Response, _admin: dict = Depends(get_current_admin)):
    for name in ("gensui_access_token", "gensui_refresh_token", "gensui_csrf_token"):
        response.delete_cookie(name, path="/")
    return {"status": "ok"}


@router.get("/me")
async def get_profile(admin: dict = Depends(get_current_admin)):
    """Get the current admin's profile."""
    return admin


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """Change the current admin's password."""
    auth = AuthService(db)
    user = await auth.get_by_id(uuid.UUID(admin["id"]))
    if user is None:
        raise HTTPException(status_code=404, detail="Admin not found")

    if not AuthService.verify_password(req.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(req.new_password) < 12:
        raise HTTPException(status_code=400, detail="New password must be at least 12 characters")

    user.password_hash = AuthService.hash_password(req.new_password)
    await db.commit()
    return {"status": "ok", "message": "Password changed successfully"}


@router.patch("/profile")
async def update_profile(
    req: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """Update the current admin's profile."""
    auth = AuthService(db)
    user = await auth.get_by_id(uuid.UUID(admin["id"]))
    if user is None:
        raise HTTPException(status_code=404, detail="Admin not found")

    if req.display_name is not None:
        user.display_name = req.display_name

    await db.commit()
    return {
        "id": str(user.id),
        "email": user.email,
        "role": user.role,
        "display_name": user.display_name,
    }


# ── Admin Management ────────────────────────────────────────

class CreateAdminRequest(BaseModel):
    email: str
    password: str
    display_name: str = "Admin"
    role: str = "admin"


class UpdateAdminRoleRequest(BaseModel):
    role: str


@router.get("/admins")
async def list_admins(
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """List all admin users."""
    auth = AuthService(db)
    admins = await auth.list_admins()
    return {
        "admins": [
            {
                "id": str(a.id),
                "email": a.email,
                "role": a.role,
                "display_name": a.display_name,
                "is_active": a.is_active,
                "last_login_at": a.last_login_at,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in admins
        ]
    }


@router.post("/admins")
async def create_admin(
    req: CreateAdminRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """Create a new admin user. Only owners and admins can create new admins."""
    # Check that current admin has sufficient privilege
    if admin.get("role") not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only owners/admins can create admins")

    if req.role not in ("owner", "admin", "auditor", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    if len(req.password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters")

    auth = AuthService(db)

    # Check if email already exists
    existing = await auth.get_by_email(req.email)
    if existing:
        raise HTTPException(status_code=409, detail="An admin with this email already exists")

    new_admin = await auth.create_admin(
        email=req.email,
        password=req.password,
        display_name=req.display_name,
        role=req.role,
    )
    await db.commit()
    return {
        "id": str(new_admin.id),
        "email": new_admin.email,
        "role": new_admin.role,
        "display_name": new_admin.display_name,
    }


@router.patch("/admins/{admin_id}/role")
async def update_admin_role(
    admin_id: str,
    req: UpdateAdminRoleRequest,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """Update an admin's role. Only owners can change roles."""
    if admin.get("role") != "owner":
        raise HTTPException(status_code=403, detail="Only owners can change admin roles")

    if req.role not in ("owner", "admin", "auditor", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role")

    auth = AuthService(db)
    user = await auth.get_by_id(uuid.UUID(admin_id))
    if user is None:
        raise HTTPException(status_code=404, detail="Admin not found")

    user.role = req.role
    await db.commit()
    return {"id": str(user.id), "email": user.email, "role": user.role}


@router.delete("/admins/{admin_id}")
async def deactivate_admin(
    admin_id: str,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(get_current_admin),
):
    """Deactivate an admin user."""
    if admin.get("role") not in ("owner",):
        raise HTTPException(status_code=403, detail="Only owners can deactivate admins")

    if admin["id"] == admin_id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")

    auth = AuthService(db)
    user = await auth.get_by_id(uuid.UUID(admin_id))
    if user is None:
        raise HTTPException(status_code=404, detail="Admin not found")

    user.is_active = False
    await db.commit()
    return {"status": "deactivated", "id": admin_id}
