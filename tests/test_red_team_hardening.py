from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import Response

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


def _request(
    path: str,
    host: str,
    headers: list[tuple[bytes, bytes]] | None = None,
    method: str = "GET",
) -> Request:
    return Request({
        "type": "http",
        "http_version": "1.1",
        "method": method,
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


@pytest.mark.asyncio
async def test_only_exact_release_identity_path_is_public_in_updates_api(monkeypatch):
    monkeypatch.setattr(settings, "deployment_mode", "server")
    monkeypatch.setattr(settings, "infrastructure_admin_token", "correct-secret")

    async def allowed(_request):
        return Response(status_code=204)

    version = await enforce_control_plane_access(
        _request("/api/v1/updates/version", "192.168.1.20"),
        allowed,
    )
    trailing_slash = await enforce_control_plane_access(
        _request("/api/v1/updates/version/", "192.168.1.20"),
        allowed,
    )
    apply_update = await enforce_control_plane_access(
        _request("/api/v1/updates/apply", "192.168.1.20"),
        allowed,
    )
    version_post = await enforce_control_plane_access(
        _request("/api/v1/updates/version", "192.168.1.20", method="POST"),
        allowed,
    )

    assert version.status_code == 204
    assert trailing_slash.status_code == 401
    assert apply_update.status_code == 401
    assert version_post.status_code == 401


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
