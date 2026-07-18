"""Shogun application settings.

Loads configuration from environment variables / .env file.
All paths, credentials, and feature flags are centralized here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Root configuration for the Shogun runtime."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "production"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    ui_port: int = 7860

    # ── Database (SQLite by default) ────────────
    database_url: str = f"sqlite+aiosqlite:///{PROJECT_ROOT}/data/shogun.db"

    # ── Qdrant (Embedded by default) ──────
    qdrant_url: str | None = None
    qdrant_path: Path = PROJECT_ROOT / "data" / "qdrant"

    # ── Security ─────────────────────────────────────────────
    secret_key: str = "change-me-to-a-random-64-char-string"
    vault_encryption_key: str = "change-me-to-a-fernet-base64-key"

    # ── Storage Paths ────────────────────────────────────────
    vault_path: Path = PROJECT_ROOT / "vault"
    log_path: Path = PROJECT_ROOT / "logs"
    config_path: Path = PROJECT_ROOT / "configs"
    uploads_path: Path = PROJECT_ROOT / "data" / "uploads"
    mado_path: Path = PROJECT_ROOT / "data" / "mado"
    ronin_path: Path = PROJECT_ROOT / "data" / "ronin"
    office_path: Path = PROJECT_ROOT / "data" / "office"
    workspace_path: Path = PROJECT_ROOT / "data" / "workspace"
    visual_artifacts_path: Path = PROJECT_ROOT / "data" / "artifacts" / "images"
    memory_exports_path: Path = PROJECT_ROOT / "data" / "memory_exports"
    memory_imports_path: Path = PROJECT_ROOT / "data" / "memory_imports"
    memory_import_max_single_file_mb: int = 2
    memory_import_max_total_mb: int = 100
    memory_import_max_files: int = 5000
    memory_allow_agent_sticky_memory: bool = True
    memory_sticky_requires_min_importance: float = 0.7
    memory_sticky_allowed_types: str = "persona,semantic,procedural,skills"
    memory_max_sticky_memories_in_context: int = 20
    memory_max_sticky_context_tokens: int = 2000
    visual_max_upload_mb: int = 20
    visual_retention_days: int = 30
    file_format_handling_enabled: bool = True
    file_detect_by_content: bool = True
    file_safe_parsing: bool = True
    file_max_preview_bytes: int = 1_048_576
    file_max_parse_bytes: int = 52_428_800
    file_max_rows_preview: int = 100
    file_max_json_depth: int = 100
    file_mask_secrets_in_preview: bool = True
    file_archive_extraction_enabled: bool = True
    file_archive_requires_approval: bool = True
    file_archive_max_uncompressed_bytes: int = 524_288_000
    file_archive_max_ratio: int = 200
    file_archive_block_executables: bool = True

    # Flow Stacking / governed hierarchical AgentFlow execution
    flow_stacking_enabled: bool = True
    flow_stacking_max_depth: int = 3
    flow_stacking_hard_max_depth: int = 5
    flow_stacking_max_child_runs_per_parent: int = 20
    flow_stacking_max_total_runs_per_root: int = 100
    flow_stacking_default_timeout_seconds: int = 600
    flow_stacking_allow_latest_version: bool = True
    flow_stacking_max_parallel_children: int = 4

    # Stack Orchestrator / long-horizon runtime control
    stack_orchestrator_enabled: bool = True
    stack_orchestrator_allow_supervised: bool = True
    stack_orchestrator_default_runtime_minutes: int = 60
    stack_orchestrator_poll_interval_seconds: float = 0.25
    stack_orchestrator_max_steps: int = 100
    stack_orchestrator_context_budget_chars: int = 16000
    stack_orchestrator_verifier_timeout_seconds: int = 90

    # Order 9: Active Skill Usage
    active_skill_usage_enabled: bool = True
    active_skill_auto_activate: bool = True
    active_skill_max_per_run: int = 5
    active_skill_max_per_step: int = 3
    active_skill_max_total_context_tokens: int = 2500
    active_skill_default_context_tokens: int = 600
    active_skill_require_exam_pass: bool = True
    active_skill_allow_failed_exams: bool = False
    active_skill_allow_deprecated: bool = False
    active_skill_preserve_during_compaction: bool = True

    # ── Telegram ─────────────────────────────────────────────
    telegram_bot_token: str | None = None
    telegram_allowed_chat_ids: str | None = None

    # Microsoft Teams command channel (secrets are references, not values)
    teams_adapter_enabled: bool = False
    teams_deployment_mode: Literal["dev", "bridge", "direct"] = "dev"
    teams_tenant_mode: Literal["single", "multi"] = "single"
    teams_allowed_tenant_ids: str = ""
    teams_bot_app_id: str | None = None
    teams_bot_client_secret_ref: str | None = None
    teams_public_messaging_endpoint: str | None = None
    teams_sso_enabled: bool = False
    teams_graph_enabled: bool = False
    teams_proactive_enabled: bool = False
    teams_manifest_valid_domains: str = ""
    teams_rate_limit_per_user_per_minute: int = 20
    teams_rate_limit_per_channel_per_minute: int = 60
    teams_high_risk_confirmation_ttl_seconds: int = 300
    teams_bridge_url: str = "http://127.0.0.1:3978"
    shogun_internal_api_url: str = "http://127.0.0.1:8000"
    shogun_internal_api_key_ref: str | None = None
    shogun_internal_api_key: str | None = None

    # ── GitHub (for update checker on private repos) ─────────
    github_token: str | None = None

    # ── Gensui Membership ────────────────────────────────────
    gensui_enabled: bool = False
    gensui_server_url: str = "http://localhost:8787"
    gensui_enrollment_token: str | None = None
    gensui_instance_name: str = "Shogun Instance"
    gensui_environment: str = "development"
    gensui_heartbeat_interval_seconds: int = 15
    gensui_command_poll_interval_seconds: int = 5
    gensui_policy_sync_interval_seconds: int = 30
    gensui_disconnect_behavior: str = "CONTINUE_LAST_POLICY"
    gensui_telemetry_mode: str = "STANDARD"
    gensui_data_path: Path = PROJECT_ROOT / "data"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def ensure_directories(self) -> None:
        """Create required filesystem directories if they don't exist."""
        for directory in [
            PROJECT_ROOT / "data",
            self.qdrant_path,
            self.vault_path,
            self.vault_path / "skills",
            self.vault_path / "snapshots",
            self.vault_path / "backups",
            self.log_path,
            self.config_path,
            self.uploads_path,
            self.visual_artifacts_path,
            self.memory_exports_path,
            self.memory_imports_path,
            # Mado browser automation directories
            self.mado_path,
            self.mado_path / "profiles",
            self.mado_path / "downloads",
            self.mado_path / "sessions",
            self.mado_path / "cache",
            self.mado_path / "screenshots",
            # Ronin desktop automation directories
            self.ronin_path,
            self.ronin_path / "screenshots",
            # Office App Mode directories
            self.office_path,
            self.office_path / "temp",
            # Agent workspace
            self.workspace_path,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


# Singleton instance
settings = Settings()
