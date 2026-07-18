"""Project-scoped programming memory learned through governed IDE work."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, UUIDMixin


class ProgrammingMemory(Base, UUIDMixin, AuditMixin):
    __tablename__ = "programming_memories"
    __table_args__ = (
        UniqueConstraint("workspace_key", "content_hash", name="uq_programming_memory_workspace_content"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    workspace_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workspace_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="solution", index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    problem: Mapped[str] = mapped_column(Text, nullable=False)
    solution: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False, default="unverified")
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    languages: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    files: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    source_urls: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    tags: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    successful_use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
