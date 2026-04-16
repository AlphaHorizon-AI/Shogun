"""Bushido ORM models — jobs, recommendations, and schedules."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, ForeignKey
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


class BushidoSchedule(Base, UUIDMixin, AuditMixin):
    """Persistent cron schedule definition for a recurring Bushido job."""

    __tablename__ = "bushido_schedules"

    # Identity
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Schedule configuration
    frequency: Mapped[str] = mapped_column(String(50), nullable=False, default="nightly")
    schedule_time: Mapped[str | None] = mapped_column(String(10), nullable=True)   # "HH:MM"
    schedule_days: Mapped[list | None] = mapped_column(JSONType(), nullable=True)   # ["mon","wed"]
    schedule_day: Mapped[int | None] = mapped_column(Integer, nullable=True)        # day-of-month
    minute_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # for hourly
    schedule_datetime: Mapped[str | None] = mapped_column(String(50), nullable=True) # ISO for one-off

    # Execution parameters
    scope: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    all_agents: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    auto_approve: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    task_instruction: Mapped[str | None] = mapped_column(String(4000), nullable=True)

    # State
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_preset: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
