"""Memory record and provenance ORM models with full salience layer."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, UUIDMixin


class MemoryRecord(Base, UUIDMixin, AuditMixin):
    __tablename__ = "memory_records"

    qdrant_point_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # Salience layer
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    importance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    decay_class: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Access tracking
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recall_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Temporal
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_recalled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Lifecycle
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MemoryProvenanceLink(Base, UUIDMixin):
    __tablename__ = "memory_provenance_links"

    child_memory_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("memory_records.id"), nullable=False)
    parent_memory_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("memory_records.id"), nullable=False)
    link_type: Mapped[str] = mapped_column(String(50), nullable=False, default="derived_from")
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
