from __future__ import annotations

import json
import logging
import socket

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from shogun.api.gensui_config import router as gensui_router
from shogun.api.infrastructure_auth import require_infrastructure_admin
from shogun.config import Settings, settings
from shogun.integrations.a2a_client import A2AClient
from shogun.services.ssrf_guard import (
    OutboundDestinationPolicy,
    SSRFValidationError,
    log_blocked_outbound_request,
    validate_outbound_url,
)


def resolver(*addresses: str):
    return lambda _host, _port: addresses


@pytest.mark.parametrize(
    ("address", "reason"),
    [
        ("169.254.169.254", "always_blocked_address"),
        ("169.254.10.1", "always_blocked_address"),
        ("fe80::1", "always_blocked_address"),
        ("fd00:ec2::254", "always_blocked_address"),
        ("224.0.0.1", "always_blocked_address"),
        ("0.0.0.0", "always_blocked_address"),
    ],
)
def test_metadata_link_local_multicast_and_unspecified_are_always_blocked(
    address: str,
    reason: str,
) -> None:
    with pytest.raises(SSRFValidationError, match="blocked address") as caught:
        validate_outbound_url(
            "https://example.test",
            policy=OutboundDestinationPolicy.LOOPBACK_ALLOWED,
            resolver=resolver(address),
        )
    assert caught.value.reason == reason


def test_public_only_accepts_public_https() -> None:
    result = validate_outbound_url(
        "https://example.test/resource",
        policy="public_only",
        resolver=resolver("93.184.216.34"),
    )
    assert result.host == "example.test"
    assert result.port == 443


@pytest.mark.parametrize("address", ["10.0.0.2", "172.16.1.2", "192.168.1.2", "fd12::2", "127.0.0.1", "::1"])
def test_public_only_blocks_private_and_loopback(address: str) -> None:
    with pytest.raises(SSRFValidationError):
        validate_outbound_url(
            "https://internal.test",
            policy="public_only",
            resolver=resolver(address),
        )


@pytest.mark.parametrize("address", ["10.0.0.2", "172.16.1.2", "192.168.1.2", "fd12::2"])
def test_private_allowed_accepts_rfc1918_and_ipv6_ula(address: str) -> None:
    result = validate_outbound_url(
        "http://internal.test:8787",
        policy="private_allowed",
        resolver=resolver(address),
    )
    assert str(result.addresses[0]) == address


@pytest.mark.parametrize("address", ["127.0.0.1", "::1"])
def test_loopback_requires_explicit_policy(address: str) -> None:
    with pytest.raises(SSRFValidationError) as caught:
        validate_outbound_url(
            "http://localhost:8787",
            policy="private_allowed",
            resolver=resolver(address),
        )
    assert caught.value.reason == "loopback_not_allowed"

    result = validate_outbound_url(
        "http://localhost:8787",
        policy="loopback_allowed",
        resolver=resolver(address),
    )
    assert result.port == 8787


def test_allowlist_supports_hostname_wildcard_ip_and_cidr() -> None:
    validate_outbound_url(
        "https://gensui.corp.example",
        policy="allowlist_only",
        allowlist="*.corp.example",
        resolver=resolver("10.1.2.3"),
    )
    validate_outbound_url(
        "https://10.2.3.4",
        policy="allowlist_only",
        allowlist="10.0.0.0/8",
        resolver=resolver("10.2.3.4"),
    )
    with pytest.raises(SSRFValidationError) as caught:
        validate_outbound_url(
            "https://other.example",
            policy="allowlist_only",
            allowlist="*.corp.example,10.0.0.0/8",
            resolver=resolver("93.184.216.34"),
        )
    assert caught.value.reason == "allowlist_miss"


def test_all_dns_answers_must_pass_policy() -> None:
    with pytest.raises(SSRFValidationError):
        validate_outbound_url(
            "https://mixed.example",
            policy="public_only",
            resolver=resolver("93.184.216.34", "127.0.0.1"),
        )


def test_ipv4_mapped_ipv6_is_normalized() -> None:
    result = validate_outbound_url(
        "http://localhost:8787",
        policy="loopback_allowed",
        resolver=resolver("::ffff:127.0.0.1"),
    )
    assert str(result.addresses[0]) == "127.0.0.1"


@pytest.mark.parametrize("url", ["file:///etc/passwd", "gopher://example.test", "data:text/plain,hello"])
def test_unsupported_schemes_are_blocked(url: str) -> None:
    with pytest.raises(SSRFValidationError) as caught:
        validate_outbound_url(url, policy="public_only", resolver=resolver("93.184.216.34"))
    assert caught.value.reason == "unsupported_scheme"


def test_embedded_credentials_and_ambiguous_numeric_hosts_are_blocked() -> None:
    with pytest.raises(SSRFValidationError) as credentials:
        validate_outbound_url(
            "https://user:secret@example.test",
            policy="public_only",
            resolver=resolver("93.184.216.34"),
        )
    assert credentials.value.reason == "embedded_credentials"

    with pytest.raises(SSRFValidationError) as numeric:
        validate_outbound_url(
            "http://2130706433",
            policy="loopback_allowed",
            resolver=resolver("127.0.0.1"),
        )
    assert numeric.value.reason == "ambiguous_numeric_host"


def test_dns_failure_and_empty_resolution_fail_closed() -> None:
    def fail_dns(_host: str, _port: int):
        raise socket.gaierror("no such host")

    with pytest.raises(SSRFValidationError) as failure:
        validate_outbound_url("https://missing.test", policy="public_only", resolver=fail_dns)
    assert failure.value.reason == "dns_failure"

    with pytest.raises(SSRFValidationError) as empty:
        validate_outbound_url("https://empty.test", policy="public_only", resolver=resolver())
    assert empty.value.reason == "dns_empty"


def test_http_and_port_policies_are_enforced() -> None:
    with pytest.raises(SSRFValidationError) as public_http:
        validate_outbound_url(
            "http://example.test",
            policy="public_only",
            resolver=resolver("93.184.216.34"),
        )
    assert public_http.value.reason == "public_http_disabled"

    with pytest.raises(SSRFValidationError) as port:
        validate_outbound_url(
            "https://example.test:22",
            policy="public_only",
            allowed_ports={443},
            resolver=resolver("93.184.216.34"),
        )
    assert port.value.reason == "blocked_port"


def test_structured_log_omits_url_secrets(caplog: pytest.LogCaptureFixture) -> None:
    exc = SSRFValidationError(
        "blocked",
        reason="allowlist_miss",
        host="gensui.example",
    )
    with caplog.at_level(logging.WARNING):
        log_blocked_outbound_request(
            exc,
            endpoint_type="gensui_test",
            destination_policy="allowlist_only",
            actor="admin-1",
            correlation_id="trace-1",
        )
    payload = json.loads(caplog.records[-1].message.removeprefix("security_event="))
    assert payload["destination_host"] == "gensui.example"
    assert payload["reason"] == "allowlist_miss"
    assert payload["timestamp"].endswith("+00:00")
    assert payload["source_integration"] == "gensui_test"
    assert "token" not in caplog.records[-1].message.casefold()


def test_server_infrastructure_routes_require_token(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()

    @app.get("/protected")
    async def protected(actor: str = Depends(require_infrastructure_admin)):
        return {"actor": actor}

    monkeypatch.setattr(settings, "deployment_mode", "server")
    monkeypatch.setattr(settings, "infrastructure_admin_token", None)
    with TestClient(app) as client:
        assert client.get("/protected").status_code == 503

        monkeypatch.setattr(settings, "infrastructure_admin_token", "correct-secret")
        assert client.get("/protected").status_code == 401
        assert client.get(
            "/protected",
            headers={"X-Shogun-Infrastructure-Token": "wrong"},
        ).status_code == 401
        response = client.get(
            "/protected",
            headers={"X-Shogun-Infrastructure-Token": "correct-secret"},
        )
        assert response.status_code == 200
        assert response.json()["actor"] == "token_admin"


def test_documented_infrastructure_token_environment_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN", "documented-secret")
    configured = Settings(_env_file=None)
    assert configured.infrastructure_admin_token == "documented-secret"


def test_invalid_outbound_port_configuration_fails_closed() -> None:
    with pytest.raises(ValidationError, match="between 1 and 65535"):
        Settings(_env_file=None, a2a_allowed_ports="443,70000")


def test_desktop_infrastructure_routes_are_loopback_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()

    @app.get("/protected")
    async def protected(actor: str = Depends(require_infrastructure_admin)):
        return {"actor": actor}

    monkeypatch.setattr(settings, "deployment_mode", "desktop")
    monkeypatch.setattr(settings, "infrastructure_admin_token", None)
    with TestClient(app, client=("team-member", 50000)) as remote_client:
        assert remote_client.get("/protected").status_code == 403
    with TestClient(app, client=("127.0.0.1", 50000)) as local_client:
        response = local_client.get("/protected")
        assert response.status_code == 200
        assert response.json()["actor"] == "local_primary_admin"


def test_gensui_route_rejects_unauthenticated_requests_before_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "deployment_mode", "server")
    monkeypatch.setattr(settings, "infrastructure_admin_token", "correct-secret")

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("unauthenticated requests must not create an outbound client")

    monkeypatch.setattr(httpx, "AsyncClient", UnexpectedClient)
    app = FastAPI()
    app.include_router(gensui_router)
    with TestClient(app) as client:
        response = client.post(
            "/gensui/connect",
            json={"server_url": "https://gensui.example"},
        )
    assert response.status_code == 401


def test_gensui_block_happens_before_outbound_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "deployment_mode", "server")
    monkeypatch.setattr(settings, "infrastructure_admin_token", "correct-secret")
    monkeypatch.setattr(settings, "gensui_destination_policy", "loopback_allowed")

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("outbound client must not be created for a blocked target")

    monkeypatch.setattr(httpx, "AsyncClient", UnexpectedClient)
    app = FastAPI()
    app.include_router(gensui_router)
    with TestClient(app) as client:
        response = client.post(
            "/gensui/test",
            json={"server_url": "http://169.254.169.254"},
            headers={"X-Shogun-Infrastructure-Token": "correct-secret"},
        )
    assert response.status_code == 200
    assert response.json()["reachable"] is False


@pytest.mark.asyncio
async def test_a2a_block_happens_before_outbound_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "a2a_destination_policy", "loopback_allowed")

    class UnexpectedClient:
        def __init__(self, *args, **kwargs):
            raise AssertionError("outbound client must not be created for a blocked target")

    monkeypatch.setattr(httpx, "AsyncClient", UnexpectedClient)
    with pytest.raises(SSRFValidationError):
        await A2AClient().send("http://169.254.169.254", {"content": "test"})


@pytest.mark.asyncio
async def test_a2a_does_not_follow_redirects(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    class RedirectingClient:
        def __init__(self, *args, follow_redirects: bool, **kwargs):
            assert follow_redirects is False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url: str):
            calls.append(url)
            return httpx.Response(
                302,
                headers={"location": "http://169.254.169.254/latest/meta-data"},
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(A2AClient, "_validate", lambda *args, **kwargs: None)
    monkeypatch.setattr(httpx, "AsyncClient", RedirectingClient)

    assert await A2AClient().ping("https://peer.example") is None
    assert calls == ["https://peer.example/api/v1/a2a/identity"]
