"""SQLAlchemy declarative base, common mixins, and portable types.

Provides backend-agnostic column types that work with both SQLite and PostgreSQL.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text, TypeDecorator, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ── Portable column types ────────────────────────────────────


class GUID(TypeDecorator):
    """Platform-agnostic UUID type.

    Uses PostgreSQL UUID natively, stores as CHAR(36) on SQLite.
    """

    impl = String(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, uuid.UUID):
                return str(value)
            return str(uuid.UUID(value))
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value)
        return value


class JSONType(TypeDecorator):
    """Platform-agnostic JSON type.

    Uses PostgreSQL JSONB natively, stores as TEXT with json
    serialization on SQLite.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value, default=lambda x: str(x) if isinstance(x, uuid.UUID) else x)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if isinstance(value, str):
                return json.loads(value)
            return value
        return value


# ── Base ─────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """Declarative base for all Shogun ORM models."""
    pass


# ── Mixins ───────────────────────────────────────────────────


class UUIDMixin:
    """Provides a UUID primary key."""

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )


class AuditMixin:
    """Provides created_at / updated_at / created_by / updated_by audit fields."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default="system",
    )
    updated_by: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default="system",
    )


class SoftDeleteMixin:
    """Provides soft-delete fields."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
