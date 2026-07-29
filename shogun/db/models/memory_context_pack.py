"""Auditable context packs produced by Phase 3 governed retrieval."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, Base, JSONType, UUIDMixin


class MemoryContextPack(Base, UUIDMixin):
    __tablename__ = "memory_context_packs"

    correlation_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="ready")
    scope_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    content_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    included_memory_ids: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    graph_expanded_memory_ids: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    excluded_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    warnings_json: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    policy_notes: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
