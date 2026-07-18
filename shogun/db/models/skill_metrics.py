"""Skill aggregated metrics ORM model — Order 15."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class SkillMetrics(Base, UUIDMixin, AuditMixin):
    """Aggregated performance metrics for a specific skill + version."""

    __tablename__ = "skill_metrics"
    __table_args__ = (
        Index("ix_skill_metrics_skill", "skill_id", "version", unique=True),
    )

    skill_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_verification_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    user_acceptance_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    average_retry_count: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_optimized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metrics_json: Mapped[dict] = mapped_column(
        JSONType(), nullable=False, default=dict
    )
