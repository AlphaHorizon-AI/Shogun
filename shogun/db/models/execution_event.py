"""Execution event ORM model — immutable audit log."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import Base, GUID, JSONType, UUIDMixin


class ExecutionEvent(Base, UUIDMixin):
    __tablename__ = "execution_events"

    mission_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False, default="info")
    summary: Mapped[str] = mapped_column(String(2000), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
