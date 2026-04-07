"""Model routing profile ORM model."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, JSONType, UUIDMixin


class ModelRoutingProfile(Base, UUIDMixin, AuditMixin):
    __tablename__ = "model_routing_profiles"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    rules: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
