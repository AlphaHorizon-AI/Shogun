"""Security policy ORM model."""

from __future__ import annotations

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, JSONType, UUIDMixin


class SecurityPolicy(Base, UUIDMixin, AuditMixin):
    __tablename__ = "security_policies"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tier: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    permissions: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    kill_switch_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    dry_run_supported: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
