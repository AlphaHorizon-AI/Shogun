"""Gensui server configuration.

Loads from environment variables / .env file.
Completely independent from Shogun's config.
"""

from __future__ import annotations

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
    gensui_server_host: str = "0.0.0.0"
    gensui_server_port: int = 8787
    debug: bool = False

    # ── Database ─────────────────────────────────────────────
    gensui_database_url: str = f"sqlite+aiosqlite:///{GENSUI_ROOT / 'data' / 'gensui.db'}"

    # ── Security ─────────────────────────────────────────────
    gensui_jwt_secret: str = "change-me-to-a-random-64-char-string"
    gensui_jwt_algorithm: str = "HS256"
    gensui_jwt_expire_hours: int = 24

    # ── Initial Admin ────────────────────────────────────────
    gensui_admin_email: str = "admin@gensui.local"
    gensui_admin_password: str = "changeme"

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
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    def validate_security(self) -> None:
        """Refuse to expose Gensui with public placeholder credentials."""

        if len(self.gensui_jwt_secret) < 32 or self.gensui_jwt_secret.startswith("change-me-"):
            raise RuntimeError("GENSUI_JWT_SECRET must be a unique random value")
        if len(self.gensui_admin_password) < 12 or self.gensui_admin_password.startswith("change-me"):
            raise RuntimeError("GENSUI_ADMIN_PASSWORD must be a unique password of at least 12 characters")


# Singleton instance
gensui_settings = GensuiSettings()
