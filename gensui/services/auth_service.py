"""Auth service — JWT generation, password hashing, admin management."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gensui.config import gensui_settings
from gensui.db.models.admin_user import AdminUser


class AuthService:
    """Authentication and admin user management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Password Hashing ─────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash."""
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

    # ── JWT Tokens ───────────────────────────────────────────

    @staticmethod
    def _create_token(admin_id: str, email: str, role: str, token_type: str) -> str:
        """Create a typed, short-lived JWT."""
        if token_type == "access":
            expires = datetime.now(timezone.utc) + timedelta(
                minutes=gensui_settings.gensui_access_token_minutes
            )
        elif token_type == "refresh":
            expires = datetime.now(timezone.utc) + timedelta(
                days=gensui_settings.gensui_refresh_token_days
            )
        else:
            raise ValueError("Unsupported token type")
        payload = {
            "sub": admin_id,
            "email": email,
            "role": role,
            "type": token_type,
            "iat": datetime.now(timezone.utc),
            "exp": expires,
            "jti": uuid.uuid4().hex,
        }
        return jwt.encode(
            payload,
            gensui_settings.jwt_secret,
            algorithm=gensui_settings.gensui_jwt_algorithm,
        )

    @staticmethod
    def create_access_token(admin_id: str, email: str, role: str) -> str:
        return AuthService._create_token(admin_id, email, role, "access")

    @staticmethod
    def create_refresh_token(admin_id: str, email: str, role: str) -> str:
        return AuthService._create_token(admin_id, email, role, "refresh")

    @staticmethod
    def create_token(admin_id: str, email: str, role: str) -> str:
        """Compatibility alias for non-browser API clients."""
        return AuthService.create_access_token(admin_id, email, role)

    @staticmethod
    def decode_token(token: str, expected_type: str = "access") -> dict:
        """Decode and validate a typed JWT token."""
        payload = jwt.decode(
            token,
            gensui_settings.jwt_secret,
            algorithms=[gensui_settings.gensui_jwt_algorithm],
        )
        if payload.get("type", "access") != expected_type:
            raise jwt.InvalidTokenError("Unexpected token type")
        return payload

    # ── Admin CRUD ───────────────────────────────────────────

    async def get_by_email(self, email: str) -> AdminUser | None:
        """Fetch an admin user by email."""
        result = await self.session.execute(
            select(AdminUser).where(AdminUser.email == email)
        )
        return result.scalars().first()

    async def get_by_id(self, admin_id: uuid.UUID) -> AdminUser | None:
        """Fetch an admin user by ID."""
        result = await self.session.execute(
            select(AdminUser).where(AdminUser.id == admin_id)
        )
        return result.scalars().first()

    async def authenticate(self, email: str, password: str) -> AdminUser | None:
        """Authenticate an admin user. Returns the user if valid, None otherwise."""
        user = await self.get_by_email(email)
        if user is None or not user.is_active:
            return None
        if not self.verify_password(password, user.password_hash):
            return None
        # Update last login
        user.last_login_at = datetime.now(timezone.utc).isoformat()
        await self.session.flush()
        return user

    async def create_admin(
        self,
        email: str,
        password: str,
        display_name: str = "Admin",
        role: str = "admin",
    ) -> AdminUser:
        """Create a new admin user."""
        admin = AdminUser(
            email=email,
            password_hash=self.hash_password(password),
            display_name=display_name,
            role=role,
        )
        self.session.add(admin)
        await self.session.flush()
        await self.session.refresh(admin)
        return admin

    async def list_admins(self) -> list[AdminUser]:
        """List all admin users."""
        result = await self.session.execute(
            select(AdminUser).where(AdminUser.is_active.is_(True))
        )
        return list(result.scalars().all())
