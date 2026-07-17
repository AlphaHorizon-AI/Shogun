"""Governed image artifacts shared by chat, Telegram, and Flow Stacks."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, SoftDeleteMixin, UUIDMixin


class ImageArtifact(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "image_artifacts"
    __table_args__ = (
        Index("ix_image_artifacts_hash_active", "sha256", "is_deleted"),
        Index("ix_image_artifacts_source_chat", "source", "source_chat_id", "created_at"),
    )

    source: Mapped[str] = mapped_column(String(40), nullable=False, default="chat")
    source_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    color_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="RGB")
    has_exif: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_path: Mapped[str] = mapped_column(Text, nullable=False)
    thumbnail_path: Mapped[str] = mapped_column(Text, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    analysis_status: Mapped[str] = mapped_column(String(30), nullable=False, default="ready")
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attached_to_memory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class ChatArtifactLink(Base, UUIDMixin, AuditMixin):
    __tablename__ = "chat_artifact_links"
    __table_args__ = (Index("ix_chat_artifact_links_context", "chat_session_id", "created_at"),)

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("image_artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chat_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    chat_message_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("chat_messages.id", ondelete="SET NULL"), nullable=True
    )
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="chat")
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class ImageAnalysis(Base, UUIDMixin, AuditMixin):
    __tablename__ = "image_analyses"
    __table_args__ = (Index("ix_image_analyses_artifact_created", "artifact_id", "created_at"),)

    artifact_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("image_artifacts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analysis_type: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    result_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_used: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
