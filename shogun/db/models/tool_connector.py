"""Tool connector ORM model."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, JSONType, SoftDeleteMixin, UUIDMixin


class ToolConnector(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "tool_connectors"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    connector_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="not_configured")
    auth_type: Mapped[str] = mapped_column(String(50), nullable=False, default="none")
    scope: Mapped[str | None] = mapped_column(String(255), nullable=True)
    risk_level: Mapped[str] = mapped_column(String(50), nullable=False, default="low")
    config: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    health_status: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
