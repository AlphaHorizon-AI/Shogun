"""Harakiri event model for recorded kill-switch actions."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from gensui.db.base import Base, UUIDMixin, JSONType


class HarakiriEvent(Base, UUIDMixin):
    """A persisted record of a Harakiri action and its mutable execution state."""

    __tablename__ = "harakiri_events"

    # individual | group | global
    scope: Mapped[str] = mapped_column(String(50), nullable=False)

    # UUID of target (shogun_id, group_id, or "global")
    target_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)  # shogun | group | global

    # soft_freeze | hard_stop | network_isolate | full_terminate
    mode: Mapped[str] = mapped_column(String(50), nullable=False, default="soft_freeze")

    # Who requested it
    requested_by: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Confirmation
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    confirmation_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    incident_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Affected targets
    affected_shogun_ids: Mapped[dict | None] = mapped_column(JSONType(), nullable=True, default=list)
    acknowledged_shogun_ids: Mapped[dict | None] = mapped_column(JSONType(), nullable=True, default=list)
    failed_shogun_ids: Mapped[dict | None] = mapped_column(JSONType(), nullable=True, default=list)

    # Status: pending | executing | completed | failed | released
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_details: Mapped[str | None] = mapped_column(String(2000), nullable=True)
