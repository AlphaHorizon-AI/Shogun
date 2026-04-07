"""Persona ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, UUIDMixin


class Persona(Base, UUIDMixin, AuditMixin):
    __tablename__ = "personas"

    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    tone: Mapped[str] = mapped_column(String(50), nullable=False)
    risk_tolerance: Mapped[str] = mapped_column(String(50), nullable=False)
    autonomy: Mapped[str] = mapped_column(String(50), nullable=False)
    verbosity: Mapped[str] = mapped_column(String(50), nullable=False)
    planning_depth: Mapped[str] = mapped_column(String(50), nullable=False)
    tool_usage_style: Mapped[str] = mapped_column(String(50), nullable=False)
    security_bias: Mapped[str] = mapped_column(String(50), nullable=False)
    memory_style: Mapped[str] = mapped_column(String(50), nullable=False)
    default_model_routing_profile_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
