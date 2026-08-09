"""Reusable, versioned Mapping / RPA templates."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, JSONType, SoftDeleteMixin, UUIDMixin


class MappingTemplate(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    __tablename__ = "mapping_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="private", index=True)
    owner_id: Mapped[str] = mapped_column(String(255), nullable=False, default="system", index=True)
    team_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    config: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
