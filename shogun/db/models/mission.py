"""Mission ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class Mission(Base, UUIDMixin, AuditMixin):
    __tablename__ = "missions"

    mission_type: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    priority: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False, default="operator")
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("agents.id"), nullable=True)
    parent_mission_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("missions.id"), nullable=True)
    root_mission_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    output_summary: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
