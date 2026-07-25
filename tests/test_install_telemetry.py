from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from shogun.telemetry.config import CONSENT_NOTICE_VERSION, HEARTBEAT_SECONDS
from shogun.telemetry.models import EventType, QueuedEvent, TelemetryEvent, TelemetryState
from shogun.telemetry.payload import build_event, enforce_payload
from shogun.telemetry.service import TelemetryService


class NoNetworkTransport:
    def __init__(self) -> None:
        self.calls = 0

    async def post_json(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("disabled telemetry must not touch the network")

    async def delete(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("disabled telemetry must not touch the network")


class CloneThenRegisterTransport:
    def __init__(self) -> None:
        self.calls = 0

    async def post_json(self, path, _payload, _token=None):
        self.calls += 1
        if path == "/v1/installations/register" and self.calls == 1:
            request = httpx.Request("POST", "https://telemetry-dev.alphahorizon.io/v1/installations/register")
            response = httpx.Response(409, request=request)
            raise httpx.HTTPStatusError("clone_conflict", request=request, response=response)
        return {
            "telemetry_token": "t" * 64,
            "heartbeat_interval_seconds": 604800,
            "schema_version": 1,
        }


def test_strict_event_schema_rejects_content_and_metadata():
    event = build_event(EventType.ACTIVE_HEARTBEAT).model_dump(mode="json")
    for key in ("prompt", "filename", "path", "email", "ip_address", "hostname", "metadata"):
        with pytest.raises(ValidationError):
            TelemetryEvent.model_validate({**event, key: "forbidden"})
        with pytest.raises(ValueError, match="Forbidden telemetry field"):
            enforce_payload({**event, key: "forbidden"})


def test_payload_has_only_approved_flat_fields():
    event = build_event(EventType.INSTALL_COMPLETED).model_dump(mode="json", exclude_none=True)
    assert set(event) == {
        "schema_version", "event_id", "event_type", "occurred_at",
        "shogun_version", "build_id", "release_channel", "distribution_channel",
        "platform_family", "architecture", "install_type", "operation_mode",
        "consent_notice_version",
    }
    enforce_payload(event)


@pytest.mark.asyncio
async def test_disabled_state_never_uses_transport(tmp_path: Path):
    service = TelemetryService(
        state_path=tmp_path / "telemetry.json",
        endpoint="https://telemetry-dev.alphahorizon.io",
    )
    transport = NoNetworkTransport()
    service.transport = transport  # type: ignore[assignment]
    await service.run_due_heartbeat()
    await service.disable()
    assert transport.calls == 0
    assert service.status()["enabled"] is False


@pytest.mark.asyncio
async def test_consent_is_explicit_random_and_versioned(tmp_path: Path):
    service = TelemetryService(
        state_path=tmp_path / "telemetry.json",
        endpoint="https://telemetry-dev.alphahorizon.io",
    )
    with pytest.raises(ValueError):
        await service.enable("0.9", actor="installer", register_immediately=False)
    await service.enable(
        CONSENT_NOTICE_VERSION,
        actor="installer",
        register_immediately=False,
    )
    state = service._load()
    assert state.enabled is True
    assert state.installation_id and state.installation_id.version == 4
    assert state.instance_nonce and state.instance_nonce.version == 4
    assert state.telemetry_token is None
    assert state.consent_actor == "installer"
    assert state.next_scheduled_at
    delta = state.next_scheduled_at - datetime.now(UTC)
    assert timedelta(days=6, hours=11) < delta < timedelta(days=7, hours=13)


def test_heartbeat_jitter_stays_within_twelve_hours():
    now = datetime.now(UTC)
    for _ in range(100):
        scheduled = TelemetryService._schedule_from(now)
        offset = (scheduled - now).total_seconds()
        assert HEARTBEAT_SECONDS - 43200 <= offset <= HEARTBEAT_SECONDS + 43200


def test_event_rejects_unknown_enum_and_nested_values():
    event = build_event(EventType.TELEMETRY_TEST).model_dump(mode="json")
    with pytest.raises(ValidationError):
        TelemetryEvent.model_validate({**event, "event_type": "runtime_details"})
    with pytest.raises(ValueError, match="Nested telemetry metadata"):
        enforce_payload({**event, "extra": {"agent_name": "hidden"}})


def test_event_id_is_random_and_idempotency_ready():
    first = build_event(EventType.ACTIVE_HEARTBEAT)
    second = build_event(EventType.ACTIVE_HEARTBEAT)
    assert first.event_id != second.event_id
    assert first.event_id.version == 4


def test_stale_consent_fails_closed_and_redacts_token(tmp_path: Path):
    path = tmp_path / "telemetry.json"
    path.write_text(TelemetryState(
        enabled=True,
        installation_id=uuid4(),
        instance_nonce=uuid4(),
        telemetry_token="never-display-this-token",
        consent_notice_version="0.9",
        consented_at=datetime.now(UTC),
        consent_actor="installer",
    ).model_dump_json(), encoding="utf-8")
    service = TelemetryService(
        state_path=path,
        endpoint="https://telemetry-dev.alphahorizon.io",
    )
    loaded = service._load()
    assert loaded.enabled is False
    assert loaded.telemetry_token is None
    assert "never-display-this-token" not in str(service.status())


def test_expired_queue_entries_are_removed(tmp_path: Path):
    path = tmp_path / "telemetry.json"
    path.write_text(TelemetryState(
        queue=[QueuedEvent(
            queued_at=datetime.now(UTC) - timedelta(days=31),
            event=build_event(EventType.UPDATE_COMPLETED, previous_version="1.0.0"),
        )],
    ).model_dump_json(), encoding="utf-8")
    service = TelemetryService(
        state_path=path,
        endpoint="https://telemetry-dev.alphahorizon.io",
    )
    assert service._load().queue == []


@pytest.mark.asyncio
async def test_clone_conflict_rotates_random_identity_once(tmp_path: Path):
    service = TelemetryService(
        state_path=tmp_path / "telemetry.json",
        endpoint="https://telemetry-dev.alphahorizon.io",
    )
    await service.enable("1.0", actor="installer", register_immediately=False)
    original = service._load().installation_id
    transport = CloneThenRegisterTransport()
    service.transport = transport  # type: ignore[assignment]
    state = service._load()
    await service._register_and_flush(state)
    rotated = service._load()
    assert rotated.installation_id != original
    assert rotated.telemetry_token == "t" * 64
    assert transport.calls == 2
