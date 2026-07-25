"""Pseudonymous telemetry persistence models."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from telemetry_service.db import Base


def now_utc() -> datetime:
    return datetime.now(UTC)


class Installation(Base):
    __tablename__ = "telemetry_installations"

    installation_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    instance_nonce_key: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_version: Mapped[str] = mapped_column(String(32))
    build_id: Mapped[str] = mapped_column(String(64))
    release_channel: Mapped[str] = mapped_column(String(24))
    distribution_channel: Mapped[str] = mapped_column(String(40))
    platform_family: Mapped[str] = mapped_column(String(16))
    architecture: Mapped[str] = mapped_column(String(24))
    install_type: Mapped[str] = mapped_column(String(24))
    operation_mode: Mapped[str] = mapped_column(String(24))
    consent_notice_version: Mapped[str] = mapped_column(String(16))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Event(Base):
    __tablename__ = "telemetry_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    installation_key: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    shogun_version: Mapped[str] = mapped_column(String(32))
    build_id: Mapped[str] = mapped_column(String(64))
    release_channel: Mapped[str] = mapped_column(String(24))
    distribution_channel: Mapped[str] = mapped_column(String(40))
    platform_family: Mapped[str] = mapped_column(String(16))
    architecture: Mapped[str] = mapped_column(String(24))
    install_type: Mapped[str] = mapped_column(String(24))
    operation_mode: Mapped[str] = mapped_column(String(24))
    schema_version: Mapped[int] = mapped_column(Integer)
    counted: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("event_id", "installation_key", name="uq_event_installation"),
    )


class ConsentHistory(Base):
    __tablename__ = "telemetry_consent_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    installation_key: Mapped[str | None] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32))
    notice_version: Mapped[str] = mapped_column(String(16))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class AdminAudit(Base):
    __tablename__ = "telemetry_admin_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
