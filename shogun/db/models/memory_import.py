"""Traceable preview, import, embedding, and rollback records for memory imports."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import Base, JSONType


class MemoryImportBatch(Base):
    __tablename__ = "memory_import_batches"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="openclaw")
    source_name: Mapped[str | None] = mapped_column(String(1000))
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="previewed", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    total_files: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedded_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    report_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class MemoryImportItem(Base):
    __tablename__ = "memory_import_items"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("memory_import_batches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_file: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="valid", index=True)
    duplicate_kind: Mapped[str | None] = mapped_column(String(40))
    duplicate_memory_id: Mapped[str | None] = mapped_column(String(36))
    shogun_memory_id: Mapped[str | None] = mapped_column(String(36), index=True)
    title: Mapped[str | None] = mapped_column(String(500))
    memory_type: Mapped[str | None] = mapped_column(String(50))
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    normalized_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    warnings_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    error_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    embedding_error: Mapped[str | None] = mapped_column(Text)
