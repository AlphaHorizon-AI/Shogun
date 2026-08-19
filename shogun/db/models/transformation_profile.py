"""Versioned registry models for deterministic transformation profiles.

Profiles are stable logical identities.  Their definitions live in immutable
version rows so SkillOpt and operators can validate, promote, retire, and roll
back mappings without overwriting the last known-good contract.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from shogun.db.base import GUID, AuditMixin, Base, JSONType, SoftDeleteMixin, UUIDMixin


class TransformationAdapter(Base, AuditMixin):
    """Runtime availability record for a profile execution adapter."""

    __tablename__ = "transformation_adapters"

    adapter_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="planned", index=True)
    implementation: Mapped[str | None] = mapped_column(String(500), nullable=True)
    capabilities: Mapped[list] = mapped_column(JSONType(), nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class RegisteredTransformationProfile(Base, UUIDMixin, AuditMixin, SoftDeleteMixin):
    """Stable identity and active pointer for one transformation profile."""

    __tablename__ = "transformation_profiles"
    __table_args__ = (
        UniqueConstraint("profile_key", name="uq_transformation_profile_key"),
        Index("ix_transformation_profile_platform_domain", "platform", "domain"),
    )

    profile_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    platform: Mapped[str] = mapped_column(String(100), nullable=False, default="generic", index=True)
    domain: Mapped[str] = mapped_column(String(100), nullable=False, default="document", index=True)
    lifecycle_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="candidate", index=True
    )
    protected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    bundled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    # Kept as a GUID without a database FK to avoid a circular DDL dependency;
    # the service owns pointer integrity transactionally.
    active_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    source_resource: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)


class TransformationProfileVersion(Base, UUIDMixin, AuditMixin):
    """Immutable profile payload plus its governed lifecycle state."""

    __tablename__ = "transformation_profile_versions"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "version_number",
            name="uq_transformation_profile_version_number",
        ),
        Index("ix_transformation_profile_version_status", "profile_id", "status"),
    )

    profile_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("transformation_profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="candidate", index=True)
    adapter_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("transformation_adapters.adapter_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    required_adapter_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="available"
    )
    origin: Mapped[str] = mapped_column(String(30), nullable=False, default="skillopt", index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    definition: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("transformation_profile_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_report: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONType(), nullable=False, default=dict)
