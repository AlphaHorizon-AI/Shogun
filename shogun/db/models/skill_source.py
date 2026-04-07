"""Skill source ORM model."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, UUIDMixin


class SkillSource(Base, UUIDMixin, AuditMixin):
    __tablename__ = "skill_sources"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, default="remote_repo")
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    default_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trust_level: Mapped[str] = mapped_column(String(50), nullable=False, default="trusted")
    sync_policy: Mapped[str] = mapped_column(String(50), nullable=False, default="manual_refresh")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
