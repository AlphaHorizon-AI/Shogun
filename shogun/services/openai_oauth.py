"""Direct ChatGPT subscription OAuth, independent of the Codex app-server."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.orm.attributes import set_committed_value

from shogun.config import settings
from shogun.db.models.model_provider import ModelProvider
from shogun.services.oauth_callback_relay import register_callback
from shogun.services.oauth_coordination import provider_oauth_lock
from shogun.services.provider_credentials import protect_provider_config, reveal_provider_secret
from shogun.services.provider_oauth import ProviderOAuthError, _validate_return_origin

AUTHORIZATION_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"
USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
TTL = 600
GRANT_KEYS = {
    "access_token",
    "refresh_token",
    "oauth_expires_at",
    "oauth_connected_at",
    "chatgpt_account_id",
    "oauth_reconnect_required",
    "oauth_client_id_used",
}


def is_openai_oauth(provider) -> bool:
    return getattr(provider, "provider_type", None) == "openai" and getattr(provider, "auth_type", None) == "oauth"


def subscription_headers(provider) -> dict[str, str]:
    if not is_openai_oauth(provider):
        return {}
    account = str((provider.config or {}).get("chatgpt_account_id") or "")
    if not account or any(ord(char) < 33 or ord(char) > 126 for char in account):
        raise ProviderOAuthError("ChatGPT account information is missing. Reconnect in The Katana.")
    return {"ChatGPT-Account-ID": account}


@dataclass
class SignInAttempt:
    provider_id: Any
    state_hash: str
    verifier: str
    redirect_uri: str
    return_origin: str
    client_id: str
    created_at: float
    status: str = "pending"
    message: str = "Complete ChatGPT sign-in in your browser."


_attempts: dict[str, SignInAttempt] = {}


def _hash(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def _prune() -> None:
    for key, attempt in list(_attempts.items()):
        if time.monotonic() - attempt.created_at > TTL:
            _attempts.pop(key, None)


def retire_attempts(provider_id) -> None:
    for key, attempt in list(_attempts.items()):
        if attempt.provider_id == provider_id:
            _attempts.pop(key, None)


def sign_in_status(provider_id, flow_id: str) -> dict:
    _prune()
    attempt = _attempts.get(_hash(flow_id))
    if not attempt or attempt.provider_id != provider_id:
        return {"status": "expired", "message": "Sign-in expired or was cancelled. Start again."}
    return {"status": attempt.status, "message": attempt.message}


def start_sign_in(provider, return_origin: str) -> dict:
    _prune()
    if not is_openai_oauth(provider) or provider.status == "disabled":
        raise ProviderOAuthError("Save an enabled OpenAI provider with ChatGPT OAuth first.")
    origin = _validate_return_origin(return_origin)
    if urlsplit(origin).hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ProviderOAuthError("Open Shogun on localhost to connect ChatGPT.")
    client_id = str((provider.config or {}).get("oauth_client_id") or settings.openai_oauth_client_id).strip()
    if not client_id:
        raise ProviderOAuthError("Configure the OpenAI OAuth public client ID before connecting.")
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    warning = None
    try:
        redirect = register_callback(
            state, f"http://127.0.0.1:{settings.api_port}/api/v1/model-providers/oauth/callback/chatgpt/{provider.id}"
        )
    except RuntimeError:
        redirect = "http://localhost:1455/auth/callback"
        warning = "Callback ports are busy. Finish consent, then paste the full localhost callback URL below."
    retire_attempts(provider.id)
    _attempts[_hash(state)] = SignInAttempt(
        provider.id,
        _hash(state),
        protect_provider_config({"secret": verifier})["secret"],
        redirect,
        origin,
        client_id,
        time.monotonic(),
    )
    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect,
        "scope": "openid profile email offline_access",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "id_token_add_organizations": "true",
        "codex_cli_simplified_flow": "true",
        "originator": "shogun",
    }
    return {
        "authorization_url": f"{AUTHORIZATION_URL}?{urlencode(query)}",
        "flow_id": state,
        "redirect_uri": redirect,
        "completion_mode": "callback",
        "manual_recovery": "paste_callback_url",
        "callback_warning": warning,
    }


def parse_callback(value: str, expected_redirect: str) -> tuple[str, str, str | None]:
    try:
        if not value or len(value) > 16384 or any(ord(char) < 32 for char in value):
            raise ValueError
        supplied, expected = urlsplit(value.strip()), urlsplit(expected_redirect)
        if (
            supplied.scheme != "http"
            or supplied.username
            or supplied.password
            or supplied.fragment
            or (supplied.hostname, supplied.port, supplied.path) != (expected.hostname, expected.port, expected.path)
        ):
            raise ValueError
        query = parse_qs(supplied.query, keep_blank_values=True, max_num_fields=12)
        if any(len(values) != 1 for values in query.values()):
            raise ValueError
        code, state, error = query.get("code", [""])[0], query.get("state", [""])[0], query.get("error", [None])[0]
        if not state or len(state) > 500 or not (code or error) or (code and error):
            raise ValueError
        return code, state, error
    except (ValueError, TypeError):
        raise ProviderOAuthError(
            "Paste the complete matching localhost callback URL, including code and state."
        ) from None


def _account_id(payload: dict) -> str | None:
    # JWT decoding supplies routing metadata only, never local proof of identity.
    for key in ("access_token", "id_token"):
        try:
            encoded = payload.get(key, "").split(".")[1]
            claims = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
            nested = claims.get("https://api.openai.com/auth") or {}
            account = claims.get("chatgpt_account_id") or nested.get("chatgpt_account_id")
            if isinstance(account, str) and 0 < len(account) <= 256 and all(33 <= ord(c) <= 126 for c in account):
                return account
        except (ValueError, IndexError, AttributeError, TypeError):
            continue
    return None


def store_tokens(provider, payload: dict, *, refresh: bool = False) -> None:
    config = dict(provider.config or {})
    if not isinstance(payload, dict):
        raise ProviderOAuthError("ChatGPT returned an invalid token response. Reconnect.")
    access, rotation = payload.get("access_token"), payload.get("refresh_token")
    try:
        expiry = int(payload.get("expires_in") or 0)
    except (TypeError, ValueError, OverflowError):
        expiry = 0
    if not isinstance(access, str) or not access.strip() or expiry <= 0:
        raise ProviderOAuthError("ChatGPT returned no usable access token or expiry. Reconnect.")
    if (rotation is not None and (not isinstance(rotation, str) or not rotation.strip())) or (
        not rotation and (not refresh or not config.get("refresh_token"))
    ):
        raise ProviderOAuthError("ChatGPT returned no refresh token. Reconnect.")
    account = _account_id(payload)
    if refresh and account and account != config.get("chatgpt_account_id"):
        raise ProviderOAuthError("ChatGPT account changed during refresh. Reconnect.")
    account = account or (config.get("chatgpt_account_id") if refresh else None)
    if not account:
        raise ProviderOAuthError("ChatGPT returned no account routing information. Reconnect.")
    if not refresh:
        config = {key: value for key, value in config.items() if key not in GRANT_KEYS}
    for key in ("api_key", "api-key", "token", "oauth_client_secret"):
        config.pop(key, None)
    config.update(
        access_token=access,
        refresh_token=rotation or config.get("refresh_token"),
        oauth_expires_at=int(time.time()) + expiry,
        oauth_connected_at=int(time.time()),
        chatgpt_account_id=account,
        oauth_reconnect_required=False,
    )
    provider.config = protect_provider_config(config)
    provider.status = "connected"
    provider.health_status = "unknown"
    provider.base_url = RESPONSES_URL


async def token_request(form: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=False) as client:
            response = await client.post(TOKEN_URL, data=form)
    except httpx.HTTPError:
        raise ProviderOAuthError("Could not reach ChatGPT. Try again shortly.") from None
    if response.status_code != 200:
        error = ProviderOAuthError(
            f"ChatGPT rejected the token request (HTTP {response.status_code}). Reconnect or try again later."
        )
        error.reconnect_required = response.status_code in {400, 401, 403}
        raise error
    try:
        if len(response.content) > 1024 * 1024:
            raise ValueError
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError
        return payload
    except ValueError:
        raise ProviderOAuthError("ChatGPT returned an unreadable token response.") from None


async def complete_sign_in(session, provider_id, *, state: str, code: str = "", error=None, callback_url=None) -> dict:
    """Both delivery paths use the same one-use attempt and credential lock."""
    async with provider_oauth_lock(session, provider_id):
        _prune()
        attempt = _attempts.get(_hash(state))
        if (
            not attempt
            or attempt.provider_id != provider_id
            or not secrets.compare_digest(attempt.state_hash, _hash(state))
        ):
            raise ProviderOAuthError("Sign-in is invalid, expired, or belongs to an older attempt. Start again.")
        if callback_url is not None:
            code, callback_state, error = parse_callback(callback_url, attempt.redirect_uri)
            if not secrets.compare_digest(_hash(callback_state), attempt.state_hash):
                raise ProviderOAuthError("Callback state does not match this sign-in.")
        if attempt.status == "success":
            return {"status": "success", "message": attempt.message}
        if attempt.status != "pending":
            raise ProviderOAuthError(attempt.message)
        provider = await session.get(ModelProvider, provider_id, populate_existing=True)
        if not provider or not is_openai_oauth(provider) or provider.status == "disabled":
            raise ProviderOAuthError("This provider changed or was removed. Start again.")
        try:
            if error or not code:
                raise ProviderOAuthError("ChatGPT sign-in was denied or cancelled. Start again when ready.")
            payload = await token_request(
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": attempt.client_id,
                    "redirect_uri": attempt.redirect_uri,
                    "code_verifier": reveal_provider_secret(attempt.verifier),
                }
            )
            store_tokens(provider, payload)
            provider.config = {**provider.config, "oauth_client_id_used": attempt.client_id}
            await session.commit()
        except BaseException:
            await session.rollback()
            attempt.status, attempt.message = "error", "ChatGPT sign-in could not complete. Start a new sign-in."
            attempt.verifier = ""
            raise
        attempt.status, attempt.message, attempt.verifier = "success", "ChatGPT connected.", ""
        return {"status": attempt.status, "message": attempt.message}


async def resolve_credential(session, provider, *, rejected_token=None) -> str:
    """Commit rotation separately; callers must resolve before flushing other writes."""
    async with provider_oauth_lock(session, provider.id):
        async with async_sessionmaker(session.bind, expire_on_commit=False)() as auth_session:
            current = await auth_session.get(ModelProvider, provider.id)
            if not current or not is_openai_oauth(current) or current.status == "disabled":
                raise ProviderOAuthError("ChatGPT provider changed or was removed. Choose it again.")
            config = current.config or {}
            if config.get("oauth_reconnect_required"):
                raise ProviderOAuthError("ChatGPT sign-in expired or was revoked. Reconnect in The Katana.")
            access = reveal_provider_secret(config.get("access_token"))
            refresh = reveal_provider_secret(config.get("refresh_token"))
            if not access or not refresh or not config.get("chatgpt_account_id"):
                raise ProviderOAuthError("ChatGPT is disconnected. Connect in The Katana.")
            try:
                expiry = int(config.get("oauth_expires_at") or 0)
            except (ValueError, TypeError):
                expiry = 0
            if expiry <= time.time() + 60 or (rejected_token and secrets.compare_digest(access, rejected_token)):
                try:
                    payload = await token_request(
                        {
                            "grant_type": "refresh_token",
                            "refresh_token": refresh,
                            "client_id": config.get("oauth_client_id_used") or settings.openai_oauth_client_id,
                        }
                    )
                    try:
                        store_tokens(current, payload, refresh=True)
                    except ProviderOAuthError as exc:
                        # A successful exchange may have rotated the grant already.
                        exc.reconnect_required = True
                        raise
                    await auth_session.commit()
                except ProviderOAuthError as exc:
                    if getattr(exc, "reconnect_required", False):
                        current.config = {**config, "oauth_reconnect_required": True}
                        current.health_status = "unhealthy"
                        await auth_session.commit()
                    raise
            # Updating the caller's view must not schedule stale credential writes.
            merged = {
                **(provider.config or {}),
                **{key: value for key, value in current.config.items() if key in GRANT_KEYS},
            }
            if inspect(provider).attrs.config.history.has_changes():
                provider.config = merged
            else:
                set_committed_value(provider, "config", merged)
            return reveal_provider_secret(current.config.get("access_token"))


async def verify_connection(session, provider) -> dict:
    try:
        access = await resolve_credential(session, provider)
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            for attempt in range(2):
                response = await client.get(
                    USAGE_URL,
                    headers={
                        "Authorization": f"Bearer {access}",
                        **subscription_headers(provider),
                        "Accept": "application/json",
                    },
                )
                if response.status_code == 401 and attempt == 0:
                    access = await resolve_credential(session, provider, rejected_token=access)
                    continue
                break
        if response.status_code != 200:
            raise ProviderOAuthError(
                f"ChatGPT connection check failed (HTTP {response.status_code}). "
                "Reconnect for 401/403; otherwise try later."
            )
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("rate_limit"), dict):
            raise ProviderOAuthError("ChatGPT returned unexpected subscription metadata.")
        return {
            "status": "ok",
            "verification": "live_subscription_check",
            "generation_tested": False,
            "note": "ChatGPT connection verified. No generation was requested."
            + (" Usage limit reached; wait for reset." if payload["rate_limit"].get("limit_reached") is True else ""),
        }
    except (httpx.HTTPError, ValueError):
        return {"status": "fail", "note": "Could not read ChatGPT subscription metadata. Try again later."}
    except ProviderOAuthError as exc:
        return {"status": "fail", "note": str(exc)}
