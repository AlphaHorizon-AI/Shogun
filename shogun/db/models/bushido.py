"""Bushido ORM models — jobs and recommendations."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class BushidoJob(Base, UUIDMixin, AuditMixin):
    __tablename__ = "bushido_jobs"

    job_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    scope: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    trigger_mode: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    output_ref: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class BushidoRecommendation(Base, UUIDMixin, AuditMixin):
    __tablename__ = "bushido_recommendations"

    job_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bushido_jobs.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    recommendation_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="low")
    approval_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
