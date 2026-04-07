"""Operator ORM model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, JSONType, UUIDMixin


class Operator(Base, UUIDMixin, AuditMixin):
    __tablename__ = "operators"

    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="owner")
    preferences: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
