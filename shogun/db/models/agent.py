"""Agent ORM model — represents both Shogun and Samurai."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shogun.db.base import AuditMixin, Base, GUID, JSONType, SoftDeleteMixin, UUIDMixin


class Agent(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "agents"

    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="draft")
    persona_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("personas.id"), nullable=True)
    kaizen_profile_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("kaizen_profiles.id"), nullable=True)
    security_policy_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("security_policies.id"), nullable=True)
    model_routing_profile_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("model_routing_profiles.id"), nullable=True)
    memory_scope: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=lambda: {"episodic": True, "semantic": True, "procedural": True, "persona": True, "skills": True})
    spawn_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    parent_agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True, default="/shogun-avatar.png")
    bushido_settings: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=lambda: {"nightly_consolidation": True, "weekly_performance_audit": True, "skill_health_check": True, "persona_drift_check": False})
    tags: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    openclaw_agent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    openclaw_api_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    persona = relationship("Persona", lazy="joined", foreign_keys=[persona_id])
    samurai_profile = relationship("SamuraiProfile", back_populates="agent", uselist=False, lazy="joined")
    routing_profile = relationship("ModelRoutingProfile", lazy="joined", foreign_keys=[model_routing_profile_id])
