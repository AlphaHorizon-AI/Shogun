"""Persistent registry for files handled by the format adapter layer."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, JSONType, UUIDMixin


class FileArtifact(Base, UUIDMixin, AuditMixin):
    __tablename__ = "file_artifacts"

    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    format_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    hash_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="workspace")
    detection_confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    detection_method: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    permissions: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    capabilities: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    warnings: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    inspection_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    last_inspected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
