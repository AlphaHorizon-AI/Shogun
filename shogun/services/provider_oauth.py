"""OAuth 2.0 Authorization Code + PKCE for model providers that support it."""

from __future__ import annotations

import base64
import hashlib
import secrets
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.model_provider import ModelProvider
from shogun.services.provider_credentials import protect_provider_config, reveal_provider_secret
from shogun.services.ssrf_guard import SSRFValidationError, validate_outbound_url

_SESSION_TTL_SECONDS = 10 * 60
_MAX_TOKEN_RESPONSE_BYTES = 1024 * 1024


class ProviderOAuthError(RuntimeError):
    """A provider OAuth flow could not be started, completed, or refreshed."""


@dataclass(frozen=True)
class OAuthSession:
    provider_id: uuid.UUID
    verifier: str
    redirect_uri: str
    return_origin: str
    created_at: float


@dataclass(frozen=True)
class OAuthFlowResult:
    provider_id: uuid.UUID
    status: str
    message: str
    created_at: float


_pending_sessions: dict[str, OAuthSession] = {}
_consuming_sessions: dict[str, OAuthSession] = {}
_flow_results: dict[str, OAuthFlowResult] = {}


def _provider_oauth_config(provider: ModelProvider) -> dict[str, Any]:
    config = provider.config or {}
    if provider.provider_type == "openai":
        raise ProviderOAuthError(
            "OpenAI does not publish an interactive end-user OAuth flow for model API access. "
            "Use an OpenAI API key or an administrator-provisioned workload identity token."
        )
    if provider.provider_type == "google":
        return {
            "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_url": "https://oauth2.googleapis.com/token",
            "scopes": config.get("oauth_scopes")
            or "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/generative-language.retriever",
        }
    if provider.provider_type == "custom":
        return {
            "authorization_url": config.get("oauth_authorization_url"),
            "token_url": config.get("oauth_token_url"),
            "scopes": config.get("oauth_scopes") or "",
        }
    raise ProviderOAuthError(f"{provider.provider_type} is not registered as an OAuth-capable model provider")


def _validated_public_destination(url: str, label: str):
    if not url:
        raise ProviderOAuthError(f"{label} is required")
    try:
        return validate_outbound_url(
            str(url),
            policy="public_only",
            allow_http_on_private_network=False,
            allow_http_on_public_network=False,
            allowed_ports=(443,),
        )
    except SSRFValidationError as exc:
        raise ProviderOAuthError(f"{label} is not an approved public HTTPS destination") from exc


def _validate_return_origin(origin: str) -> str:
    parsed = urlsplit(origin)
    hostname = (parsed.hostname or "").casefold()
    is_loopback = hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise ProviderOAuthError("OAuth return origin must contain only scheme, host, and port")
    if parsed.scheme == "https" and hostname:
        return origin.rstrip("/")
    if parsed.scheme == "http" and is_loopback:
        return origin.rstrip("/")
    raise ProviderOAuthError("OAuth results can return only to HTTPS or a loopback development origin")


def _redirect_uri(provider: ModelProvider) -> str:
    configured = str((provider.config or {}).get("oauth_redirect_uri") or "").strip()
    if configured:
        parsed = urlsplit(configured)
        if parsed.scheme == "https" or (
            parsed.scheme == "http" and (parsed.hostname or "").casefold() in {"localhost", "127.0.0.1", "::1"}
        ):
            return configured
        raise ProviderOAuthError("OAuth redirect URI must use HTTPS or a loopback HTTP address")
    return f"http://127.0.0.1:{settings.api_port}/api/v1/model-providers/oauth/callback"


def _prune_sessions() -> None:
    cutoff = time.time() - _SESSION_TTL_SECONDS
    for state, session in list(_pending_sessions.items()):
        if session.created_at < cutoff:
            _pending_sessions.pop(state, None)
    for state, session in list(_consuming_sessions.items()):
        if session.created_at < cutoff:
            _consuming_sessions.pop(state, None)
    for state, result in list(_flow_results.items()):
        if result.created_at < cutoff:
            _flow_results.pop(state, None)


def _record_flow_result(state: str, pending: OAuthSession, status: str, message: str) -> None:
    _pending_sessions.pop(state, None)
    _consuming_sessions.pop(state, None)
    _flow_results[state] = OAuthFlowResult(pending.provider_id, status, message, time.time())


def provider_oauth_status(provider_id: uuid.UUID, flow_id: str) -> dict[str, str]:
    """Return the bounded, non-secret status of one browser OAuth attempt."""

    _prune_sessions()
    pending = _pending_sessions.get(flow_id) or _consuming_sessions.get(flow_id)
    if pending and pending.provider_id == provider_id:
        return {"status": "pending", "message": "Waiting for provider authorization"}
    result = _flow_results.get(flow_id)
    if result and result.provider_id == provider_id:
        return {"status": result.status, "message": result.message}
    return {"status": "expired", "message": "OAuth authorization expired or is no longer available"}


def reject_provider_oauth(state: str, message: str) -> tuple[uuid.UUID, str]:
    """Finish a provider-declined flow so the desktop UI can stop polling."""

    _prune_sessions()
    pending = _pending_sessions.get(state) or _consuming_sessions.get(state)
    if not pending:
        raise ProviderOAuthError("OAuth state is invalid or expired")
    _record_flow_result(state, pending, "error", message)
    return pending.provider_id, pending.return_origin


def accept_provider_oauth(state: str) -> None:
    """Publish success only after the encrypted provider tokens are committed."""

    pending = _consuming_sessions.get(state)
    if not pending:
        raise ProviderOAuthError("OAuth state is invalid or expired")
    _record_flow_result(state, pending, "success", "OAuth connection completed")


def start_provider_oauth(provider: ModelProvider, return_origin: str) -> dict[str, Any]:
    """Create a one-use OAuth state and browser authorization URL."""

    if provider.auth_type != "oauth":
        raise ProviderOAuthError("Save this provider with OAuth authentication before connecting it")
    config = provider.config or {}
    client_id = str(config.get("oauth_client_id") or "").strip()
    if not client_id:
        raise ProviderOAuthError("OAuth client ID is required")
    oauth = _provider_oauth_config(provider)
    authorization = _validated_public_destination(str(oauth.get("authorization_url") or ""), "OAuth authorization URL")
    _validated_public_destination(str(oauth.get("token_url") or ""), "OAuth token URL")
    return_origin = _validate_return_origin(return_origin)
    redirect_uri = _redirect_uri(provider)

    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(32)
    _prune_sessions()
    _pending_sessions[state] = OAuthSession(provider.id, verifier, redirect_uri, return_origin, time.time())

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": str(oauth.get("scopes") or ""),
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    if provider.provider_type == "google":
        params.update({"access_type": "offline", "prompt": "consent"})
    return {
        "authorization_url": f"{authorization.url}{'&' if '?' in authorization.url else '?'}{urlencode(params)}",
        "redirect_uri": redirect_uri,
        "flow_id": state,
    }


async def _post_token(url: str, form: dict[str, str]) -> dict[str, Any]:
    destination = _validated_public_destination(url, "OAuth token URL")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "Host": destination.host_header,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            response = await client.post(
                destination.pinned_url,
                data=form,
                headers=headers,
                extensions=destination.request_extensions,
            )
    except httpx.HTTPError as exc:
        raise ProviderOAuthError("Could not reach the provider OAuth token endpoint") from exc
    if len(response.content) > _MAX_TOKEN_RESPONSE_BYTES:
        raise ProviderOAuthError("Provider OAuth token response was too large")
    try:
        payload = response.json()
    except ValueError as exc:
        raise ProviderOAuthError("Provider OAuth token endpoint returned invalid JSON") from exc
    if response.status_code >= 400:
        message = payload.get("error_description") or payload.get("error") or f"HTTP {response.status_code}"
        raise ProviderOAuthError(f"Provider rejected the OAuth token request: {message}")
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise ProviderOAuthError("Provider OAuth response did not contain an access token")
    return payload


def _store_token_payload(provider: ModelProvider, payload: dict[str, Any]) -> None:
    current = dict(provider.config or {})
    updated = dict(current)
    updated["access_token"] = str(payload["access_token"])
    if payload.get("refresh_token"):
        updated["refresh_token"] = str(payload["refresh_token"])
    if payload.get("token_type"):
        updated["oauth_token_type"] = str(payload["token_type"])
    if payload.get("scope"):
        updated["oauth_granted_scopes"] = str(payload["scope"])
    try:
        expires_in = max(0, int(payload.get("expires_in") or 0))
    except (TypeError, ValueError):
        expires_in = 0
    updated["oauth_expires_at"] = int(time.time()) + expires_in if expires_in else None
    updated["oauth_connected_at"] = int(time.time())
    provider.config = protect_provider_config(updated, current)
    provider.status = "connected"


async def complete_provider_oauth(
    session: AsyncSession,
    *,
    state: str,
    code: str,
) -> tuple[ModelProvider, str]:
    """Consume OAuth state, exchange the code, and persist encrypted tokens."""

    _prune_sessions()
    pending = _pending_sessions.pop(state, None)
    if not pending:
        raise ProviderOAuthError("OAuth state is invalid or expired")
    _consuming_sessions[state] = pending
    try:
        provider = await session.get(ModelProvider, pending.provider_id)
        if not provider:
            raise ProviderOAuthError("OAuth provider no longer exists")
        oauth = _provider_oauth_config(provider)
        config = provider.config or {}
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": pending.redirect_uri,
            "client_id": str(config.get("oauth_client_id") or ""),
            "code_verifier": pending.verifier,
        }
        client_secret = reveal_provider_secret(config.get("oauth_client_secret"))
        if client_secret:
            form["client_secret"] = client_secret
        payload = await _post_token(str(oauth.get("token_url") or ""), form)
        _store_token_payload(provider, payload)
        await session.flush()
    except ProviderOAuthError as exc:
        _record_flow_result(state, pending, "error", str(exc))
        raise
    except Exception:
        _record_flow_result(state, pending, "error", "OAuth connection could not be completed")
        raise
    return provider, pending.return_origin


async def ensure_provider_access_token(session: AsyncSession, provider: ModelProvider) -> str | None:
    """Return an OAuth token, refreshing it shortly before expiry when possible."""

    config = provider.config or {}
    access_token = reveal_provider_secret(config.get("access_token"))
    if provider.auth_type != "oauth":
        return access_token
    try:
        expires_at = int(config.get("oauth_expires_at") or 0)
    except (TypeError, ValueError):
        expires_at = 0
    if access_token and (not expires_at or expires_at > int(time.time()) + 60):
        return access_token
    refresh_token = reveal_provider_secret(config.get("refresh_token"))
    if not refresh_token:
        return access_token
    oauth = _provider_oauth_config(provider)
    form = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": str(config.get("oauth_client_id") or ""),
    }
    client_secret = reveal_provider_secret(config.get("oauth_client_secret"))
    if client_secret:
        form["client_secret"] = client_secret
    payload = await _post_token(str(oauth.get("token_url") or ""), form)
    _store_token_payload(provider, payload)
    await session.flush()
    return reveal_provider_secret(provider.config.get("access_token"))


def disconnect_provider_oauth(provider: ModelProvider) -> None:
    """Remove only OAuth grants while retaining non-secret provider settings."""

    removed = {
        "access_token",
        "refresh_token",
        "oauth_token_type",
        "oauth_granted_scopes",
        "oauth_expires_at",
        "oauth_connected_at",
    }
    provider.config = {key: value for key, value in (provider.config or {}).items() if key not in removed}
    provider.status = "not_configured"
