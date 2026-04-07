"""Runtime session ORM model."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import Base, JSONType, UUIDMixin


class RuntimeSession(Base, UUIDMixin):
    __tablename__ = "runtime_sessions"

    session_type: Mapped[str] = mapped_column(String(50), nullable=False, default="system")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="offline")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    runtime_version: Mapped[str] = mapped_column(String(50), nullable=False, default="0.1.0")
    host: Mapped[str] = mapped_column(String(255), nullable=False, default="localhost")
    health: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
