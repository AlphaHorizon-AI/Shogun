"""Gensui server configuration.

Loads from environment variables / .env file.
Completely independent from Shogun's config.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

GENSUI_ROOT = Path(__file__).resolve().parent


class GensuiSettings(BaseSettings):
    """Root configuration for the Gensui server."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Server ───────────────────────────────────────────────
    gensui_server_host: str = "127.0.0.1"
    gensui_server_port: int = 8787
    debug: bool = False

    # ── Database ─────────────────────────────────────────────
    gensui_database_url: str = f"sqlite+aiosqlite:///{GENSUI_ROOT / 'data' / 'gensui.db'}"

    # ── Security ─────────────────────────────────────────────
    # Raw values remain supported for backwards compatibility. New installs
    # use a mounted secret file so signing material is not stored in .env.
    gensui_jwt_secret: str | None = None
    gensui_jwt_secret_file: Path = GENSUI_ROOT / "data" / "secrets" / "jwt_secret"
    gensui_jwt_algorithm: str = "HS256"
    gensui_access_token_minutes: int = 15
    gensui_refresh_token_days: int = 7
    gensui_cookie_secure: bool = False
    gensui_trusted_proxies: str = ""

    # ── Initial Admin ────────────────────────────────────────
    gensui_admin_email: str = "admin@gensui.local"
    gensui_admin_password: str = "changeme"
    gensui_allow_insecure_local_password: bool = False

    # ── Enrollment ───────────────────────────────────────────
    gensui_require_enrollment_approval: bool = True
    gensui_default_posture: str = "STANDARD"

    # ── Telemetry ────────────────────────────────────────────
    gensui_telemetry_default_mode: str = "STANDARD"

    # ── Harakiri Controls ────────────────────────────────────
    gensui_enable_global_harakiri: bool = True
    gensui_enable_group_harakiri: bool = True
    gensui_enable_individual_harakiri: bool = True

    # ── Heartbeat ────────────────────────────────────────────
    gensui_heartbeat_timeout_seconds: int = 60

    # ── Paths ────────────────────────────────────────────────
    gensui_data_path: Path = GENSUI_ROOT / "data"
    gensui_log_path: Path = GENSUI_ROOT / "logs"
    gensui_frontend_dist: Path = GENSUI_ROOT / "frontend" / "dist"

    def ensure_directories(self) -> None:
        """Create required filesystem directories."""
        for directory in [
            self.gensui_data_path,
            self.gensui_log_path,
            self.gensui_jwt_secret_file.parent,
        ]:
            directory.mkdir(parents=True, exist_ok=True)
        if not self.gensui_jwt_secret and not self.gensui_jwt_secret_file.exists():
            secret = secrets.token_urlsafe(64) + "\n"
            try:
                descriptor = os.open(
                    self.gensui_jwt_secret_file,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
            except FileExistsError:
                pass
            else:
                with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                    handle.write(secret)

    @property
    def jwt_secret(self) -> str:
        """Resolve JWT signing material from a mounted file or legacy env value."""
        if self.gensui_jwt_secret:
            return self.gensui_jwt_secret.strip()
        try:
            return self.gensui_jwt_secret_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise RuntimeError("Gensui JWT secret file is unavailable") from exc

    def validate_security(self) -> None:
        """Refuse to expose Gensui with public placeholder credentials."""

        secret = self.jwt_secret
        if len(secret) < 32 or secret.startswith("change-me-"):
            raise RuntimeError("Gensui JWT signing secret must be a unique random value")
        weak_admin_password = (
            len(self.gensui_admin_password) < 12
            or self.gensui_admin_password.startswith("change-me")
        )
        if weak_admin_password and self.gensui_allow_insecure_local_password:
            if self.gensui_server_host not in {"127.0.0.1", "localhost", "::1"}:
                raise RuntimeError(
                    "GENSUI_ALLOW_INSECURE_LOCAL_PASSWORD may only be used with a loopback server host"
                )
            return
        if weak_admin_password:
            raise RuntimeError("GENSUI_ADMIN_PASSWORD must be a unique password of at least 12 characters")

# Singleton instance
gensui_settings = GensuiSettings()
