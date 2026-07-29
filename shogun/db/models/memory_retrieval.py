"""Auditable Phase 1 cascade retrieval diagnostics."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import Base, GUID, JSONType, UUIDMixin


class MemoryRetrievalRun(Base, UUIDMixin):
    __tablename__ = "memory_retrieval_runs"

    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="started")
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    scope_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    plan_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    stages_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    result_memory_ids: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    excluded_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
