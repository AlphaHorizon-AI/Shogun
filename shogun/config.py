"""Shogun application settings.

Loads configuration from environment variables / .env file.
All paths, credentials, and feature flags are centralized here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Root configuration for the Shogun runtime."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    ui_port: int = 7860

    # ── Database (SQLite by default — zero install) ────────────
    # For production PostgreSQL: "postgresql+asyncpg://user:pass@host:5432/shogun"
    database_url: str = "sqlite+aiosqlite:///./data/shogun.db"

    # ── Qdrant (Embedded by default — no Docker needed) ──────
    # Set to "http://localhost:6333" to use a standalone Qdrant server
    qdrant_url: str | None = None
    qdrant_path: Path = Path("./data/qdrant")

    # ── Security ─────────────────────────────────────────────
    secret_key: str = "change-me-to-a-random-64-char-string"
    vault_encryption_key: str = "change-me-to-a-fernet-base64-key"

    # ── Storage Paths ────────────────────────────────────────
    vault_path: Path = Path("./vault")
    log_path: Path = Path("./logs")
    config_path: Path = Path("./configs")

    # ── Telegram ─────────────────────────────────────────────
    telegram_bot_token: str | None = None
    telegram_allowed_chat_ids: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def ensure_directories(self) -> None:
        """Create required filesystem directories if they don't exist."""
        for directory in [
            Path("./data"),
            self.qdrant_path,
            self.vault_path,
            self.vault_path / "skills",
            self.vault_path / "snapshots",
            self.vault_path / "backups",
            self.log_path,
            self.config_path,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()
