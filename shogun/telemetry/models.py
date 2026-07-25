"""Strict version-one installation telemetry models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventType(str, Enum):
    INSTALL_COMPLETED = "install_completed"
    UPDATE_COMPLETED = "update_completed"
    ACTIVE_HEARTBEAT = "active_heartbeat"
    CONSENT_REVOKED = "consent_revoked"
    TELEMETRY_TEST = "telemetry_test"


class ReleaseChannel(str, Enum):
    STABLE = "stable"
    BETA = "beta"
    DEVELOPMENT = "development"


class DistributionChannel(str, Enum):
    OFFICIAL_INSTALLER = "official_installer"
    OFFICIAL_DOCKER = "official_docker"
    SOURCE_CHECKOUT = "source_checkout"
    AUTHORIZED_COMMUNITY_BUILD = "authorized_community_build"
    UNKNOWN = "unknown"


class PlatformFamily(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    OTHER = "other"


class InstallType(str, Enum):
    NATIVE = "native"
    DOCKER = "docker"
    HEADLESS_SERVER = "headless_server"
    DEVELOPMENT = "development"


class OperationMode(str, Enum):
    SINGLE_USER = "single_user"
    TEAM = "team"


class TelemetryEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    event_id: UUID
    event_type: EventType
    occurred_at: datetime
    shogun_version: str = Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z.+-]+$")
    build_id: str = Field(min_length=1, max_length=64, pattern=r"^[0-9A-Za-z._-]+$")
    release_channel: ReleaseChannel
    distribution_channel: DistributionChannel
    platform_family: PlatformFamily
    architecture: str = Field(min_length=1, max_length=24, pattern=r"^[0-9A-Za-z_-]+$")
    install_type: InstallType
    operation_mode: OperationMode
    consent_notice_version: str = Field(min_length=1, max_length=16, pattern=r"^[0-9.]+$")
    previous_version: str | None = Field(
        default=None, min_length=1, max_length=32, pattern=r"^[0-9A-Za-z.+-]+$"
    )

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a UTC offset")
        return value


class RegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    installation_id: UUID
    instance_nonce: UUID
    consent_notice_version: str = Field(min_length=1, max_length=16, pattern=r"^[0-9.]+$")
    shogun_version: str = Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-z.+-]+$")
    build_id: str = Field(min_length=1, max_length=64, pattern=r"^[0-9A-Za-z._-]+$")
    release_channel: ReleaseChannel
    distribution_channel: DistributionChannel
    platform_family: PlatformFamily
    architecture: str = Field(min_length=1, max_length=24, pattern=r"^[0-9A-Za-z_-]+$")
    install_type: InstallType
    operation_mode: OperationMode


class RegistrationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telemetry_token: str = Field(min_length=32, max_length=512)
    heartbeat_interval_seconds: int = Field(ge=5 * 24 * 60 * 60, le=14 * 24 * 60 * 60)
    schema_version: Literal[1] = 1


class SubmissionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "accepted", "duplicate", "invalid", "revoked", "unsupported_schema", "retry_after"
    ]
    accepted: int = Field(default=0, ge=0, le=10)


class QueuedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queued_at: datetime
    event: TelemetryEvent


class TelemetryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    prompt_dismissed: bool = False
    installation_id: UUID | None = None
    instance_nonce: UUID | None = None
    telemetry_token: str | None = None
    consent_notice_version: str | None = None
    consented_at: datetime | None = None
    consent_actor: Literal["local_administrator", "primary_admin", "installer"] | None = None
    last_sent_at: datetime | None = None
    next_scheduled_at: datetime | None = None
    last_result: str | None = None
    last_reported_version: str | None = None
    queue: list[QueuedEvent] = Field(default_factory=list, max_length=5)
