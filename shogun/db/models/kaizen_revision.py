"""KaizenRevision ORM model — tracks revision history for governance documents."""

from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, UUIDMixin


class KaizenRevision(Base, UUIDMixin, AuditMixin):
    __tablename__ = "kaizen_revisions"

    document_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "constitution" | "mandate"
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    change_summary: Mapped[str] = mapped_column(String(1000), nullable=False, default="Initial version")
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False, default="")
