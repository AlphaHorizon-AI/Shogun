"""Shogun bare-bones application settings.

Centralizes configuration for AgentFlow, AI Providers, Routing Profiles, and Local Folder setup.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKIP_ENV_FILE = os.environ.get("SHOGUN_SKIP_ENV_FILE", "").casefold() in {
    "1",
    "true",
    "yes",
    "on",
}


def normalize_database_url(value: str) -> str:
    """Anchor relative SQLite databases to the Shogun installation."""
    url = make_url(str(value))
    if not url.get_backend_name().startswith("sqlite"):
        return str(value)

    database = url.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return str(value)

    database_path = Path(database)
    if not database_path.is_absolute():
        database_path = (PROJECT_ROOT / database_path).resolve()
    return url.set(database=database_path.as_posix()).render_as_string(hide_password=False)


class Settings(BaseSettings):
    """Minimal runtime configuration for Shogun AgentFlow."""

    model_config = SettingsConfigDict(
        env_file=None if SKIP_ENV_FILE else str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "production"
    deployment_mode: Literal["desktop", "server"] = "desktop"
    debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    openai_oauth_client_id: str = "app_EMoamEEZ73f0CkXaXp7hrann"

    # ── Database (SQLite by default) ─────────────────────────
    database_url: str = f"sqlite+aiosqlite:///{PROJECT_ROOT}/data/shogun.db"

    @field_validator("database_url", mode="before")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    # ── Security ─────────────────────────────────────────────
    secret_key: str = "change-me-to-a-random-64-char-string"
    vault_encryption_key: str = "change-me-to-a-fernet-base64-key"
    infrastructure_admin_token: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN",
            "INFRASTRUCTURE_ADMIN_TOKEN",
        ),
    )
    outbound_allowlist: str = ""
    allow_http_on_private_network: bool = True
    allow_http_on_public_network: bool = False

    # ── Storage & Local Folder Paths ─────────────────────────
    vault_path: Path = PROJECT_ROOT / "vault"
    log_path: Path = PROJECT_ROOT / "logs"
    config_path: Path = PROJECT_ROOT / "configs"
    uploads_path: Path = PROJECT_ROOT / "data" / "uploads"
    workspace_path: Path = PROJECT_ROOT / "data" / "workspace"
    office_path: Path = PROJECT_ROOT / "data" / "office"
    mado_path: Path = PROJECT_ROOT / "data" / "mado"
    memory_exports_path: Path = PROJECT_ROOT / "data" / "exports"
    memory_imports_path: Path = PROJECT_ROOT / "data" / "imports"
    agent_flow_document_max_chars: int = 5_000_000

    # ── File Format & Archive Limits ─────────────────────────
    file_format_handling_enabled: bool = True
    file_detect_by_content: bool = True
    file_max_parse_bytes: int = 25 * 1024 * 1024
    file_max_preview_bytes: int = 512 * 1024
    file_max_rows_preview: int = 200
    file_max_json_depth: int = 20
    file_mask_secrets_in_preview: bool = True
    file_archive_extraction_enabled: bool = True
    file_archive_max_uncompressed_bytes: int = 100 * 1024 * 1024
    file_archive_max_ratio: float = 100.0
    file_archive_requires_approval: bool = False

    # ── AgentFlow Execution & Stack Limits ───────────────────
    flow_stacking_enabled: bool = False
    flow_stacking_allow_latest_version: bool = True
    flow_stacking_max_depth: int = 3
    flow_stacking_hard_max_depth: int = 5
    flow_stacking_max_child_runs_per_parent: int = 20
    flow_stacking_max_parallel_children: int = 5
    flow_stacking_max_total_runs_per_root: int = 50
    flow_stacking_default_timeout_seconds: int = 600
    stack_orchestrator_enabled: bool = False
    stack_orchestrator_allow_supervised: bool = True
    stack_orchestrator_max_steps: int = 20
    stack_orchestrator_context_budget_chars: int = 32_000
    stack_orchestrator_poll_interval_seconds: float = 1.0
    stack_orchestrator_verifier_timeout_seconds: int = 120
    active_skill_max_per_run: int = 5
    active_skill_max_per_step: int = 3

    @property
    def workspace_config_file(self) -> Path:
        return Path(self.config_path) / "workspace.json"

    def load_persisted_workspace(self) -> None:
        """Apply persisted local workspace folder path if configured by the operator."""
        cfg_file = self.workspace_config_file
        if not cfg_file.is_file():
            return
        try:
            payload = json.loads(cfg_file.read_text(encoding="utf-8"))
            raw_path = str(payload.get("workspace_path") or "").strip()
            if raw_path:
                self.workspace_path = Path(os.path.expandvars(os.path.expanduser(raw_path))).resolve()
        except Exception:
            pass

    def save_persisted_workspace(self, folder_path: Path) -> Path:
        """Persist the chosen local workspace folder path and ensure subdirectories exist."""
        import tempfile

        normalized = os.path.normpath(os.path.abspath(str(folder_path)))
        allowed_roots = (
            os.path.realpath(str(Path.home())),
            os.path.realpath(str(PROJECT_ROOT.parent)),
            os.path.realpath(tempfile.gettempdir()),
        )
        for root in allowed_roots:
            if normalized == root:
                os.makedirs(root, exist_ok=True)
                os.makedirs(os.path.join(root, "input"), exist_ok=True)
                os.makedirs(os.path.join(root, "output"), exist_ok=True)
                resolved = Path(root)
                self.workspace_path = resolved
                cfg_file = self.workspace_config_file
                cfg_file.parent.mkdir(parents=True, exist_ok=True)
                cfg_file.write_text(json.dumps({"workspace_path": root}, indent=2), encoding="utf-8")
                return resolved
            if normalized.startswith(root + os.sep):
                rel = normalized[len(root) + len(os.sep) :]
                candidate = os.path.normpath(os.path.join(root, rel))
                if candidate.startswith(root + os.sep):
                    os.makedirs(candidate, exist_ok=True)
                    os.makedirs(os.path.join(candidate, "input"), exist_ok=True)
                    os.makedirs(os.path.join(candidate, "output"), exist_ok=True)
                    resolved = Path(candidate)
                    self.workspace_path = resolved
                    cfg_file = self.workspace_config_file
                    cfg_file.parent.mkdir(parents=True, exist_ok=True)
                    cfg_file.write_text(json.dumps({"workspace_path": candidate}, indent=2), encoding="utf-8")
                    return resolved
        raise ValueError("Workspace folder must be inside user home, project directory, or temp folder")

    def validate_security(self) -> None:
        """Fail closed when a server deployment still uses bootstrap secrets."""
        if self.deployment_mode != "server":
            return
        invalid: list[str] = []
        if len(self.secret_key) < 32 or self.secret_key.casefold().startswith("change-me"):
            invalid.append("SECRET_KEY")
        if len(self.vault_encryption_key) < 32 or self.vault_encryption_key.casefold().startswith("change-me"):
            invalid.append("VAULT_ENCRYPTION_KEY")
        if (
            not self.infrastructure_admin_token
            or len(self.infrastructure_admin_token) < 32
            or self.infrastructure_admin_token.casefold().startswith("change-me")
        ):
            invalid.append("SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN")
        if invalid:
            raise RuntimeError("Secure server configuration required for: " + ", ".join(invalid))

    def ensure_directories(self) -> None:
        """Create required filesystem directories if they don't exist."""
        self.load_persisted_workspace()
        for directory in [
            PROJECT_ROOT / "data",
            self.vault_path,
            self.log_path,
            self.config_path,
            self.uploads_path,
            self.workspace_path,
            self.workspace_path / "input",
            self.workspace_path / "output",
        ]:
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.load_persisted_workspace()
