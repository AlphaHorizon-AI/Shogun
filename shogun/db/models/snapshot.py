"""Snapshot ORM model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, UUIDMixin


class Snapshot(Base, UUIDMixin, AuditMixin):
    __tablename__ = "snapshots"

    snapshot_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
