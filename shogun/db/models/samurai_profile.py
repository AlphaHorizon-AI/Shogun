"""Samurai capability profile ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class SamuraiProfile(Base, UUIDMixin, AuditMixin):
    __tablename__ = "samurai_profiles"

    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("agents.id"), unique=True, nullable=False)
    role_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("samurai_roles.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    specializations: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    allowed_task_types: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    blocked_task_types: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    max_parallel_jobs: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    auto_spawnable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    agent = relationship("Agent", back_populates="samurai_profile", foreign_keys=[agent_id])
    samurai_role = relationship("SamuraiRole", lazy="joined")
