"""Immutable protocol and scheduling configuration for installation telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shogun.config import settings

SCHEMA_VERSION = 1
CONSENT_NOTICE_VERSION = "1.0"
PRODUCTION_ENDPOINT = "https://telemetry.alphahorizon.io"
PRIVACY_NOTICE_URL = "https://www.alphahorizon.io/shogun/telemetry-privacy/"
HEARTBEAT_SECONDS = 7 * 24 * 60 * 60
HEARTBEAT_JITTER_SECONDS = 12 * 60 * 60
MAX_EVENT_BYTES = 4 * 1024
MAX_BATCH_BYTES = 32 * 1024
MAX_BATCH_EVENTS = 10
MAX_QUEUE_EVENTS = 5
QUEUE_TTL_DAYS = 30


@dataclass(frozen=True)
class TelemetryConfig:
    endpoint: str
    state_path: Path
    development: bool


def load_config() -> TelemetryConfig:
    """Return a fixed production endpoint; overrides exist only outside production."""
    endpoint = PRODUCTION_ENDPOINT
    if not settings.is_production:
        endpoint = {
            "development": "https://telemetry-dev.alphahorizon.io",
            "staging": "https://telemetry-staging.alphahorizon.io",
        }.get(settings.app_env, PRODUCTION_ENDPOINT)
    return TelemetryConfig(
        endpoint=endpoint,
        state_path=settings.config_path / "telemetry.json",
        development=not settings.is_production,
    )
