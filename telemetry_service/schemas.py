"""Server-side strict schemas and body limits."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from shogun.telemetry.models import RegistrationRequest, TelemetryEvent


class EventBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[TelemetryEvent] = Field(min_length=1, max_length=10)


class RegistrationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telemetry_token: str
    heartbeat_interval_seconds: int = 604800
    schema_version: int = 1


class EventResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    accepted: int = 0


__all__ = [
    "EventBatch", "EventResult", "RegistrationRequest", "RegistrationResult",
]
