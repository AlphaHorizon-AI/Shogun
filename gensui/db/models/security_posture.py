"""Security posture model — named policy configurations defining what a Shogun is allowed to do."""

from __future__ import annotations

from sqlalchemy import String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from gensui.db.base import Base, UUIDMixin, AuditMixin, JSONType


class SecurityPosture(Base, UUIDMixin, AuditMixin):
    """A security posture definition with enforcement rules."""

    __tablename__ = "security_postures"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Severity level: 0 = most permissive (OPEN), higher = more restrictive
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Whether this is a built-in posture (cannot be deleted)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Created by admin ID
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True, default="system")

    # ── Rules ────────────────────────────────────────────────
    # JSON array of policy rules that define what is allowed/blocked
    rules_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True, default=dict)

    # ── Quick-access permission flags ────────────────────────
    # These are derived from rules_json but stored for fast lookup
    allow_external_models: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_local_models: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_tool_execution: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_mado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_memory_write: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_memory_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_agent_flow: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_nexus: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_samurai_delegation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_scheduled_triggers: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_autonomous_loops: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_external_web: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_file_write: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_external_api: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Per-tool overrides — Campaign Preset style ({"send_email": "block", "desktop_click": "confirm"})
    tool_overrides_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True, default=dict)

    # Advanced parameter/content matching rules distributed with ToolGate policy
    advanced_toolgate_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True, default=dict)
