"""Skill installation record ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shogun.db.base import Base, GUID, UUIDMixin


class SkillInstallation(Base, UUIDMixin):
    __tablename__ = "skill_installations"

    skill_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("skills.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, default="global")
    target_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="installed")
    installed_version: Mapped[str] = mapped_column(String(50), nullable=False)
    auto_update: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    quarantine_status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    last_health_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    installed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    installed_by: Mapped[str] = mapped_column(String(255), nullable=False, default="operator")

    skill = relationship("Skill", lazy="joined")
