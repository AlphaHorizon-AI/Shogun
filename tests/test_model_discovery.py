from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from shogun.services import model_discovery
from shogun.services.model_discovery import (
    ModelDiscoveryError,
    _catalog_headers,
    _parse_catalog,
    discover_provider_models,
)


def test_parse_catalog_supports_openai_and_google_shapes() -> None:
    assert _parse_catalog(
        "openai",
        {"data": [{"id": "gpt-z"}, {"id": "gpt-a"}, {"id": "gpt-z"}]},
    ) == ["gpt-a", "gpt-z"]
    assert _parse_catalog(
        "google",
        {"models": [{"name": "models/gemini-pro"}, {"name": "models/gemini-flash"}]},
    ) == ["gemini-flash", "gemini-pro"]


def test_catalog_headers_use_provider_specific_authentication() -> None:
    assert _catalog_headers("openai", "secret")["Authorization"] == "Bearer secret"
    anthropic_headers = _catalog_headers("anthropic", "secret")
    assert anthropic_headers["x-api-key"] == "secret"
    assert anthropic_headers["anthropic-version"] == "2023-06-01"
    assert "Authorization" not in anthropic_headers


@pytest.mark.asyncio
async def test_discovery_uses_pinned_destination_and_disables_redirects(monkeypatch) -> None:
    destination = SimpleNamespace(
        pinned_url="https://203.0.113.10/v1/models",
        host_header="api.example.test",
        request_extensions={"sni_hostname": "api.example.test"},
    )
    validation: dict[str, object] = {}
    client_options: dict[str, object] = {}
    request: dict[str, object] = {}

    def fake_validate(url: str, **kwargs):
        validation.update(url=url, **kwargs)
        return destination

    class FakeClient:
        def __init__(self, **kwargs):
            client_options.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url: str, **kwargs):
            request.update(url=url, **kwargs)
            return httpx.Response(200, json={"data": [{"id": "model-b"}, {"id": "model-a"}]})

    monkeypatch.setattr(model_discovery, "validate_outbound_url", fake_validate)
    monkeypatch.setattr(model_discovery.httpx, "AsyncClient", FakeClient)

    result = await discover_provider_models(
        provider_type="openai",
        base_url="https://api.example.test/v1/",
        api_key="secret",
    )

    assert result == ["model-a", "model-b"]
    assert validation == {
        "url": "https://api.example.test/v1/models",
        "policy": "public_only",
        "allow_http_on_private_network": False,
        "allow_http_on_public_network": False,
        "allowed_ports": (443,),
    }
    assert client_options["follow_redirects"] is False
    assert request["url"] == destination.pinned_url
    assert request["headers"]["Host"] == destination.host_header
    assert request["headers"]["Authorization"] == "Bearer secret"
    assert request["extensions"] == destination.request_extensions


@pytest.mark.asyncio
async def test_discovery_returns_safe_error_for_rejected_credentials(monkeypatch) -> None:
    destination = SimpleNamespace(
        pinned_url="https://203.0.113.10/v1/models",
        host_header="api.example.test",
        request_extensions={"sni_hostname": "api.example.test"},
    )

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            return httpx.Response(401, json={"error": "do not expose this provider response"})

    monkeypatch.setattr(model_discovery, "validate_outbound_url", lambda *_args, **_kwargs: destination)
    monkeypatch.setattr(model_discovery.httpx, "AsyncClient", FakeClient)

    with pytest.raises(ModelDiscoveryError, match="rejected the credential"):
        await discover_provider_models(
            provider_type="openai",
            base_url="https://api.example.test/v1",
            api_key="invalid",
        )
