"""Skill publication history ORM model — Order 15."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class SkillPublication(Base, UUIDMixin, AuditMixin):
    """Records each publication event for a skill version to a provider."""

    __tablename__ = "skill_publications"
    __table_args__ = (
        Index("ix_skill_publication_skill", "skill_id", "version"),
    )

    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, default="local")
    published_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    publication_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    response_json: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
