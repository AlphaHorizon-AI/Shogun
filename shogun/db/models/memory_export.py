"""Traceable jobs and items for portable memory exports."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import Base, JSONType


class MemoryExportJob(Base):
    __tablename__ = "memory_export_jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False, default="local_user")
    filters_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    counts_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    output_dir: Mapped[str | None] = mapped_column(String(1000))
    zip_path: Mapped[str | None] = mapped_column(String(1000))
    error_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class MemoryExportItem(Base):
    __tablename__ = "memory_export_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    export_job_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("memory_export_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    output_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    error: Mapped[str | None] = mapped_column(Text)
