"""Minimal SecurityPolicy ORM model stub."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, JSONType, UUIDMixin


class SecurityPolicy(Base, UUIDMixin, AuditMixin):
    __tablename__ = "security_policies"

    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    policy_type: Mapped[str] = mapped_column(String(100), default="posture")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    rules: Mapped[dict[str, Any]] = mapped_column(JSONType(), default=dict)
