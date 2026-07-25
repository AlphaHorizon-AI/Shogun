"""Allowlisted payload construction and privacy release gates."""

from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from shogun import __version__
from shogun.config import settings
from shogun.telemetry.config import CONSENT_NOTICE_VERSION, MAX_EVENT_BYTES
from shogun.telemetry.models import (
    DistributionChannel,
    EventType,
    InstallType,
    OperationMode,
    PlatformFamily,
    RegistrationRequest,
    ReleaseChannel,
    TelemetryEvent,
)

FORBIDDEN_KEYS = frozenset(
    {
        "prompt", "response", "message", "email", "calendar", "contact", "username",
        "user_name", "first_name", "last_name", "organization_name", "company",
        "hostname", "host_name", "machine_id", "mac", "serial", "file", "filename",
        "path", "directory", "memory", "agent_name", "workflow_name", "tool_input",
        "tool_output", "credential", "password", "secret", "token", "api_key",
        "telegram", "teams_user", "ip_address", "url", "browser_history", "screenshot",
        "metadata", "stack_trace",
    }
)


def _version_metadata() -> dict:
    version_path = Path(__file__).resolve().parents[2] / "version.json"
    try:
        return json.loads(version_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"version": __version__, "build": "unknown", "channel": "stable"}


def platform_family() -> PlatformFamily:
    return {
        "Windows": PlatformFamily.WINDOWS,
        "Linux": PlatformFamily.LINUX,
        "Darwin": PlatformFamily.MACOS,
    }.get(platform.system(), PlatformFamily.OTHER)


def architecture() -> str:
    value = platform.machine().lower().replace("amd64", "x86_64").replace("aarch64", "arm64")
    return value if value in {"x86_64", "x86", "arm64", "arm"} else "other"


def runtime_dimensions() -> dict:
    metadata = _version_metadata()
    docker = settings.deployment_mode == "server"
    team_mode = docker
    try:
        setup = json.loads(
            (settings.config_path / "setup.json").read_text(encoding="utf-8")
        )
        team_mode = setup.get("installation_mode") == "team"
    except (OSError, ValueError):
        pass
    distribution = (
        DistributionChannel.OFFICIAL_DOCKER
        if docker
        else DistributionChannel.OFFICIAL_INSTALLER
    )
    if settings.app_env == "development":
        distribution = DistributionChannel.SOURCE_CHECKOUT
    return {
        "shogun_version": str(metadata.get("version") or __version__),
        "build_id": str(metadata.get("build") or "unknown"),
        "release_channel": ReleaseChannel(str(metadata.get("channel") or "stable")),
        "distribution_channel": distribution,
        "platform_family": platform_family(),
        "architecture": architecture(),
        "install_type": (
            InstallType.HEADLESS_SERVER
            if settings.deployment_mode == "server"
            else InstallType.DEVELOPMENT
            if settings.app_env == "development"
            else InstallType.NATIVE
        ),
        "operation_mode": (
            OperationMode.TEAM if team_mode else OperationMode.SINGLE_USER
        ),
    }


def build_event(
    event_type: EventType,
    *,
    notice_version: str = CONSENT_NOTICE_VERSION,
    previous_version: str | None = None,
) -> TelemetryEvent:
    event = TelemetryEvent(
        event_id=uuid4(),
        event_type=event_type,
        occurred_at=datetime.now(UTC),
        consent_notice_version=notice_version,
        previous_version=previous_version,
        **runtime_dimensions(),
    )
    enforce_payload(event.model_dump(mode="json", exclude_none=True))
    return event


def build_registration(installation_id, instance_nonce, notice_version: str) -> RegistrationRequest:
    return RegistrationRequest(
        installation_id=installation_id,
        instance_nonce=instance_nonce,
        consent_notice_version=notice_version,
        **runtime_dimensions(),
    )


def enforce_payload(value: object) -> None:
    """Reject forbidden/nested keys and over-sized canonical JSON."""
    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                lowered = str(key).casefold()
                if lowered in FORBIDDEN_KEYS:
                    raise ValueError(f"Forbidden telemetry field: {key}")
                if isinstance(child, (dict, list)):
                    raise ValueError("Nested telemetry metadata is prohibited")
        elif isinstance(node, list):
            for child in node:
                walk(child)

    walk(value)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if len(encoded) > MAX_EVENT_BYTES:
        raise ValueError("Telemetry event exceeds the 4 KB limit")
