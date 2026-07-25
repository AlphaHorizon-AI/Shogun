"""Shogun member model — a registered Shogun instance under Gensui control."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

from gensui.db.base import Base, UUIDMixin, AuditMixin, GUID, JSONType


class ShogunMember(Base, UUIDMixin, AuditMixin):
    """A Shogun instance that has enrolled into this Gensui server."""

    __tablename__ = "shogun_members"

    # ── Identity ─────────────────────────────────────────────
    instance_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    environment: Mapped[str] = mapped_column(String(50), nullable=False, default="development")
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    build_hash: Mapped[str | None] = mapped_column(String(100), nullable=True)
    public_key: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    member_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # ── Enrollment ───────────────────────────────────────────
    # pending | active | disabled | revoked
    enrollment_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")

    # ── Status ───────────────────────────────────────────────
    # online | offline | unknown
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Security Posture ─────────────────────────────────────
    default_posture_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    individual_posture_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)
    effective_posture_id: Mapped[str | None] = mapped_column(GUID(), nullable=True)

    # ── Harakiri ─────────────────────────────────────────────
    # none | soft_freeze | hard_stop | network_isolate | full_terminate
    harakiri_state: Mapped[str] = mapped_column(String(50), nullable=False, default="none")

    # ── Reported Capabilities ────────────────────────────────
    local_os: Mapped[str | None] = mapped_column(String(100), nullable=True)
    deployment_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    samurai_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_workflow_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active_mado_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Metadata (flexible JSON) ─────────────────────────────
    metadata_json: Mapped[dict | None] = mapped_column(JSONType(), nullable=True, default=dict)

    # ── Disconnect behavior ──────────────────────────────────
    disconnect_behavior: Mapped[str] = mapped_column(
        String(50), nullable=False, default="CONTINUE_LAST_POLICY"
    )
