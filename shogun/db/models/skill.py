"""Skill definition ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shogun.db.base import AuditMixin, Base, GUID, JSONType, SoftDeleteMixin, UUIDMixin


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
    hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    local_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    source = relationship("SkillSource", lazy="joined")
