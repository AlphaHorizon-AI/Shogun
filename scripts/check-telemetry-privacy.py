"""Release gate for the immutable version-one telemetry privacy contract."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shogun.telemetry.config import (  # noqa: E402
    CONSENT_NOTICE_VERSION,
    HEARTBEAT_SECONDS,
    PRODUCTION_ENDPOINT,
)
from shogun.telemetry.models import (  # noqa: E402
    RegistrationRequest,
    TelemetryEvent,
    TelemetryState,
)

EXPECTED_EVENT_FIELDS = {
    "schema_version", "event_id", "event_type", "occurred_at", "shogun_version",
    "build_id", "release_channel", "distribution_channel", "platform_family",
    "architecture", "install_type", "operation_mode", "consent_notice_version",
    "previous_version",
}
EXPECTED_REGISTRATION_FIELDS = {
    "schema_version", "installation_id", "instance_nonce", "consent_notice_version",
    "shogun_version", "build_id", "release_channel", "distribution_channel",
    "platform_family", "architecture", "install_type", "operation_mode",
}

assert set(TelemetryEvent.model_fields) == EXPECTED_EVENT_FIELDS
assert set(RegistrationRequest.model_fields) == EXPECTED_REGISTRATION_FIELDS
assert "metadata" not in TelemetryEvent.model_fields
assert TelemetryState().enabled is False
assert PRODUCTION_ENDPOINT == "https://telemetry.alphahorizon.io"
assert HEARTBEAT_SECONDS == 604800
assert CONSENT_NOTICE_VERSION == "1.0"
print("Telemetry privacy contract verified")
