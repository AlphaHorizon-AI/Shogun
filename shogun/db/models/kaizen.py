"""Kaizen profile ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, JSONType, UUIDMixin


class KaizenProfile(Base, UUIDMixin, AuditMixin):
    __tablename__ = "kaizen_profiles"

    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
    content: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    change_summary: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
