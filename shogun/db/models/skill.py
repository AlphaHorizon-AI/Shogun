"""Skill definition ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shogun.db.base import GUID, AuditMixin, Base, JSONType, SoftDeleteMixin, UUIDMixin


class Skill(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "skills"

    source_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("skill_sources.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="0.0.1")
    skill_type: Mapped[str] = mapped_column(String(50), nullable=False, default="single")
    manifest: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trust_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="available")
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    exam_status: Mapped[str] = mapped_column(String(30), nullable=False, default="untested")
    tags: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    triggers: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    use_when: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    avoid_when: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    requires_tools: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    minimum_posture: Mapped[str] = mapped_column(String(30), nullable=False, default="guarded")
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    conflict_group: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_hint: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_context_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=600)
    activation_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="advisory")
    body_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    brief_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_checklist: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Order 15: OpenClaw College Content Loop ──────────────────
    lifecycle_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default="draft"
    )
    publication_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="unpublished"
    )
    active_version_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("skill_versions.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    source = relationship("SkillSource", lazy="joined")

    @property
    def description(self) -> str:
        """Return the canonical description stored in the skill manifest.

        Skill descriptions predate the active-skill pipeline and are persisted
        in ``manifest`` rather than in a dedicated database column.  Exposing
        this compatibility property keeps model consumers aligned with that
        storage contract without duplicating data or requiring a migration.
        """
        manifest = self.manifest or {}
        return str(manifest.get("description") or manifest.get("purpose") or "")

    @description.setter
    def description(self, value: str | None) -> None:
        manifest = dict(self.manifest or {})
        manifest["description"] = value or ""
        self.manifest = manifest
