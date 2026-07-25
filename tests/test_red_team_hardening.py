from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from gensui.api.commands import get_pending_commands
from gensui.api.deps import get_shogun_identity
from gensui.services.member_service import MemberService
from shogun.api.a2a import InboundEnvelope, _check_a2a_replay, _seen_signatures
from shogun.api.control_plane_auth import enforce_control_plane_access
from shogun.config import settings
from shogun.schemas.models import ModelProviderResponse
from shogun.schemas.tools import ToolConnectorResponse
from shogun.services.provider_credentials import (
    protect_provider_config,
    provider_api_key,
)
from shogun.services.ssrf_guard import SSRFValidationError, validate_outbound_url


def _request(path: str, host: str, headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": headers or [],
        "client": (host, 1234),
        "server": ("shogun", 8000),
    })


@pytest.mark.asyncio
async def test_desktop_control_plane_rejects_remote_clients(monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "desktop")
    monkeypatch.setattr(settings, "infrastructure_admin_token", None)

    async def allowed(_request):
        return Response(status_code=204)

    response = await enforce_control_plane_access(
        _request("/api/v1/model-providers", "192.168.1.20"),
        allowed,
    )
    assert response.status_code == 503


@pytest.mark.asyncio
async def test_desktop_control_plane_requires_token_on_loopback(monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "desktop")
    monkeypatch.setattr(settings, "infrastructure_admin_token", "correct-secret")

    async def allowed(_request):
        return Response(status_code=204)

    denied = await enforce_control_plane_access(
        _request("/api/v1/model-providers", "127.0.0.1"),
        allowed,
    )
    accepted = await enforce_control_plane_access(
        _request(
            "/api/v1/model-providers",
            "127.0.0.1",
            [(b"x-shogun-infrastructure-token", b"correct-secret")],
        ),
        allowed,
    )
    assert denied.status_code == 401
    assert accepted.status_code == 204


@pytest.mark.asyncio
async def test_server_control_plane_requires_configured_admin_token(monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "server")
    monkeypatch.setattr(settings, "infrastructure_admin_token", "correct-secret")

    async def allowed(_request):
        return Response(status_code=204)

    denied = await enforce_control_plane_access(
        _request("/api/v1/model-providers", "192.168.1.20"),
        allowed,
    )
    accepted = await enforce_control_plane_access(
        _request(
            "/api/v1/model-providers",
            "192.168.1.20",
            [(b"x-shogun-infrastructure-token", b"correct-secret")],
        ),
        allowed,
    )
    assert denied.status_code == 401
    assert accepted.status_code == 204


def test_model_provider_response_redacts_nested_credentials():
    response = ModelProviderResponse.model_validate({
        "id": uuid.uuid4(),
        "provider_type": "openrouter",
        "name": "Provider",
        "slug": "provider",
        "base_url": "https://example.test",
        "auth_type": "api_key",
        "is_local": False,
        "status": "connected",
        "health_status": "healthy",
        "config": {"api_key": "secret", "nested": {"token": "secret", "model": "safe"}},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })

    exported = response.model_dump()
    assert exported["config"]["api_key"] == "********"
    assert exported["config"]["nested"] == {"token": "********", "model": "safe"}


def test_tool_connector_response_redacts_nested_credentials():
    response = ToolConnectorResponse.model_validate({
        "id": uuid.uuid4(),
        "name": "Connector",
        "slug": "connector",
        "connector_type": "api",
        "source": "manual",
        "base_url": "https://example.test",
        "auth_type": "none",
        "risk_level": "low",
        "config": {"authorization": "secret", "nested": {"password": "secret"}},
        "status": "connected",
        "health_status": "healthy",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    })
    exported = response.model_dump()
    assert exported["config"]["authorization"] == "********"
    assert exported["config"]["nested"]["password"] == "********"


def test_provider_credentials_are_encrypted_and_recoverable():
    protected = protect_provider_config({"api_key": "provider-secret", "model": "safe"})
    assert protected["api_key"].startswith("enc:")
    assert "provider-secret" not in protected["api_key"]
    assert provider_api_key(protected) == "provider-secret"
    retained = protect_provider_config({"api_key": "********"}, protected)
    assert retained["api_key"] == protected["api_key"]


def test_server_security_validation_rejects_bootstrap_configuration(monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "server")
    monkeypatch.setattr(settings, "secret_key", "change-me-to-a-random-64-char-string")
    monkeypatch.setattr(settings, "vault_encryption_key", "change-me-to-a-fernet-base64-key")
    monkeypatch.setattr(settings, "infrastructure_admin_token", None)
    with pytest.raises(RuntimeError):
        settings.validate_security()


def test_a2a_replay_window_rejects_stale_and_repeated_messages():
    _seen_signatures.clear()
    stale = InboundEnvelope(
        from_name="peer",
        from_url="https://peer.example",
        workspace_id=str(uuid.uuid4()),
        message_type="message",
        content="hello",
        ts=0,
        sig="stale-signature",
    )
    with pytest.raises(HTTPException) as stale_error:
        _check_a2a_replay(stale)
    assert stale_error.value.status_code == 403

    current = stale.model_copy(update={"ts": int(datetime.now(timezone.utc).timestamp()), "sig": "seen"})
    _check_a2a_replay(current)
    _seen_signatures[current.sig] = datetime.now(timezone.utc).timestamp()
    with pytest.raises(HTTPException) as replay_error:
        _check_a2a_replay(current)
    assert replay_error.value.status_code == 409


def test_loopback_only_destination_policy_rejects_private_network():
    with pytest.raises(SSRFValidationError) as exc_info:
        validate_outbound_url(
            "http://model.internal:11434/api/tags",
            policy="loopback_only",
            resolver=lambda _host, _port: ["10.10.1.9"],
        )
    assert exc_info.value.reason == "non_loopback_address"


@pytest.mark.asyncio
async def test_gensui_member_auth_requires_matching_secret(monkeypatch):
    member_id = uuid.uuid4()
    secret = "s" * 48
    member = SimpleNamespace(
        id=member_id,
        instance_name="member",
        enrollment_status="active",
        member_token_hash=hashlib.sha256(secret.encode("ascii")).hexdigest(),
    )

    async def fake_get_by_id(_service, _member_id):
        return member

    monkeypatch.setattr(MemberService, "get_by_id", fake_get_by_id)

    with pytest.raises(HTTPException) as exc_info:
        await get_shogun_identity(str(member_id), "wrong", object())
    assert exc_info.value.status_code == 401

    identity = await get_shogun_identity(str(member_id), secret, object())
    assert identity["shogun_id"] == str(member_id)


@pytest.mark.asyncio
async def test_gensui_command_poll_cannot_cross_member_boundary():
    requested = uuid.uuid4()
    result = await get_pending_commands(
        requested,
        db=object(),
        identity={"shogun_id": str(uuid.uuid4())},
    )
    assert result == []
