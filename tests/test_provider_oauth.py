from __future__ import annotations

import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from shogun.db.models.model_provider import ModelProvider
from shogun.services.provider_credentials import protect_provider_config, reveal_provider_secret
from shogun.services.provider_oauth import (
    ProviderOAuthError,
    accept_provider_oauth,
    complete_provider_oauth,
    provider_oauth_status,
    reject_provider_oauth,
    start_provider_oauth,
)


def _provider(provider_type: str, config: dict) -> ModelProvider:
    return ModelProvider(
        id=uuid.uuid4(),
        provider_type=provider_type,
        name=provider_type.title(),
        slug=f"{provider_type}-{uuid.uuid4()}",
        auth_type="oauth",
        is_local=False,
        status="not_configured",
        config=config,
    )


def test_oauth_client_secret_is_encrypted() -> None:
    protected = protect_provider_config({"oauth_client_secret": "client-secret"})

    assert protected["oauth_client_secret"].startswith("enc:")
    assert reveal_provider_secret(protected["oauth_client_secret"]) == "client-secret"


def test_openai_interactive_oauth_is_rejected() -> None:
    with pytest.raises(ProviderOAuthError, match="does not publish an interactive"):
        start_provider_oauth(
            _provider("openai", {"oauth_client_id": "client-id"}),
            "http://127.0.0.1:5173",
        )


def test_google_oauth_uses_authorization_code_pkce(monkeypatch: pytest.MonkeyPatch) -> None:
    def approve(url: str, _label: str):
        return SimpleNamespace(url=url)

    monkeypatch.setattr("shogun.services.provider_oauth._validated_public_destination", approve)
    provider = _provider("google", {"oauth_client_id": "desktop-client"})
    result = start_provider_oauth(
        provider,
        "http://127.0.0.1:5173",
    )
    query = parse_qs(urlsplit(result["authorization_url"]).query)

    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["desktop-client"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0]
    assert query["state"][0]
    assert query["access_type"] == ["offline"]
    assert result["redirect_uri"].endswith("/api/v1/model-providers/oauth/callback")
    assert provider_oauth_status(provider.id, result["flow_id"])["status"] == "pending"

    rejected_provider_id, return_origin = reject_provider_oauth(result["flow_id"], "access_denied")

    assert rejected_provider_id == provider.id
    assert return_origin == "http://127.0.0.1:5173"
    assert provider_oauth_status(provider.id, result["flow_id"]) == {
        "status": "error",
        "message": "access_denied",
    }


@pytest.mark.asyncio
async def test_oauth_success_is_published_after_token_storage(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _provider("google", {"oauth_client_id": "desktop-client"})

    def approve(url: str, _label: str):
        return SimpleNamespace(url=url)

    async def token_response(_url: str, _form: dict[str, str]):
        return {"access_token": "provider-access-token", "expires_in": 3600}

    class Session:
        async def get(self, _model, provider_id):
            return provider if provider_id == provider.id else None

        async def flush(self):
            return None

    monkeypatch.setattr("shogun.services.provider_oauth._validated_public_destination", approve)
    monkeypatch.setattr("shogun.services.provider_oauth._post_token", token_response)
    result = start_provider_oauth(provider, "http://127.0.0.1:5173")

    await complete_provider_oauth(Session(), state=result["flow_id"], code="authorization-code")

    assert provider_oauth_status(provider.id, result["flow_id"])["status"] == "pending"
    accept_provider_oauth(result["flow_id"])
    assert provider_oauth_status(provider.id, result["flow_id"])["status"] == "success"
    with pytest.raises(ProviderOAuthError, match="invalid or expired"):
        await complete_provider_oauth(Session(), state=result["flow_id"], code="replayed-code")
