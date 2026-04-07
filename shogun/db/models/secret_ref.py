"""Secret reference ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import AuditMixin, Base, GUID, UUIDMixin


class SecretRef(Base, UUIDMixin, AuditMixin):
    __tablename__ = "secret_refs"

    owner_type: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    secret_type: Mapped[str] = mapped_column(String(50), nullable=False)
    key_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(100), nullable=False, default="encrypted_local_vault")
    last_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active")
