"""Model provider ORM model."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, JSONType, UUIDMixin


class ModelProvider(Base, UUIDMixin, AuditMixin):
    __tablename__ = "model_providers"

    provider_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False, default="api_key")
    is_local: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="not_configured")
    health_status: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    config: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
