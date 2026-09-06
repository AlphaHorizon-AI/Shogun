"""Direct ChatGPT OAuth regressions using isolated databases and synthetic tokens."""

import asyncio
import base64
import hashlib
import json
import logging
import uuid
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.api.chatgpt_oauth import cancel_sign_in
from shogun.api.model_providers import disconnect_oauth, update_provider
from shogun.db.base import Base
from shogun.db.models.model_provider import ModelProvider
from shogun.schemas.models import ModelProviderResponse, ModelProviderUpdate
from shogun.services import openai_oauth as oauth
from shogun.services.chatgpt_transport import responses_payload
from shogun.services.model_service import ModelProviderService
from shogun.services.model_transport import model_chat_completion, model_chat_stream
from shogun.services.oauth_callback_relay import OAuthCallbackLogFilter
from shogun.services.provider_credentials import reveal_provider_secret
from shogun.services.provider_oauth import ProviderOAuthError


def token(account="account-one"):
    claims = (
        base64.urlsafe_b64encode(json.dumps({"https://api.openai.com/auth": {"chatgpt_account_id": account}}).encode())
        .decode()
        .rstrip("=")
    )
    return f"synthetic.{claims}.signature"


def grant(account="account-one", refresh="synthetic-refresh"):
    return {"access_token": token(account), "refresh_token": refresh, "expires_in": 3600}


@pytest.fixture
async def database(tmp_path, monkeypatch):
    from shogun.services.event_logger import EventLogger

    async def no_audit(*_args, **_kwargs):
        return None

    monkeypatch.setattr(EventLogger, "emit_auth_event", no_audit)
    monkeypatch.setattr(oauth.settings, "vault_path", tmp_path / "vault")
    monkeypatch.setattr(oauth, "register_callback", lambda *_: "http://localhost:1455/auth/callback")
    oauth._attempts.clear()
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'oauth.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        provider = ModelProvider(
            id=uuid.uuid4(),
            provider_type="openai",
            name="Synthetic ChatGPT",
            slug="synthetic",
            auth_type="oauth",
            is_local=False,
            status="not_configured",
            config={"models": ["test-model"], "oauth_client_id": "test-public-client"},
        )
        session.add(provider)
        await session.commit()
        provider_id = provider.id
    yield factory, provider_id
    await engine.dispose()
    oauth._attempts.clear()


def callback(flow, **extra):
    return flow["redirect_uri"] + "?" + urlencode({"code": "one-use-code", "state": flow["flow_id"], **extra})


async def connected(database):
    factory, provider_id = database
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        oauth.store_tokens(provider, grant())
        await session.commit()
    return factory, provider_id


async def test_pkce_and_no_plaintext_verifier(database):
    factory, provider_id = database
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        flow = oauth.start_sign_in(provider, "http://localhost:5173")
    query = parse_qs(urlsplit(flow["authorization_url"]).query)
    attempt = oauth._attempts[oauth._hash(flow["flow_id"])]
    verifier = reveal_provider_secret(attempt.verifier)
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    assert query["code_challenge"] == [expected]
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["openid profile email offline_access"]
    assert attempt.verifier.startswith("enc:")
    assert flow["flow_id"] not in oauth._attempts
    assert provider.status == "not_configured"


@pytest.mark.parametrize(
    "value",
    [
        "bare-token",
        "https://localhost:1455/auth/callback?code=c&state=s",
        "http://evil.example:1455/auth/callback?code=c&state=s",
        "http://localhost:1457/auth/callback?code=c&state=s",
        "http://localhost:1455/other?code=c&state=s",
        "http://user@localhost:1455/auth/callback?code=c&state=s",
        "http://localhost:1455/auth/callback?code=c&state=s#fragment",
        "http://localhost:1455/auth/callback?code=c&code=d&state=s",
        "http://localhost:1455/auth/callback?code=c&state=s&state=s",
        "http://localhost:1455/auth/callback?code=c&state=s&error=denied",
        "http://localhost:1455/auth/callback?code=c",
        "x" * 16385,
    ],
)
def test_recovery_parser_rejects_invalid_urls(value):
    with pytest.raises(ProviderOAuthError):
        oauth.parse_callback(value, "http://localhost:1455/auth/callback")


async def test_manual_and_browser_race_exchange_once(database, monkeypatch):
    factory, provider_id = database
    calls = []

    async def exchange(form):
        calls.append(form)
        await asyncio.sleep(0.02)
        return grant()

    monkeypatch.setattr(oauth, "token_request", exchange)
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        flow = oauth.start_sign_in(provider, "http://localhost:5173")

    async def finish(manual):
        async with factory() as session:
            return await oauth.complete_sign_in(
                session,
                provider_id,
                state=flow["flow_id"],
                code="one-use-code",
                callback_url=callback(flow) if manual else None,
            )

    results = await asyncio.gather(finish(True), finish(False))
    assert all(result["status"] == "success" for result in results)
    assert len(calls) == 1
    assert calls[0]["redirect_uri"] == flow["redirect_uri"]
    assert "client_secret" not in calls[0]
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        assert provider.status == "connected"
        assert provider.config["access_token"].startswith("enc:")
        assert provider.config["refresh_token"].startswith("enc:")
        assert provider.config["models"] == ["test-model"]
        public = ModelProviderResponse.model_validate(provider).model_dump_json()
        assert token() not in public and "synthetic-refresh" not in public


async def test_invalid_state_and_invalid_link_preserve_pending(database):
    factory, provider_id = database
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        flow = oauth.start_sign_in(provider, "http://localhost:5173")
        for url in ["bad-url", callback(flow, state="wrong-state")]:
            with pytest.raises(ProviderOAuthError):
                await oauth.complete_sign_in(session, provider_id, state=flow["flow_id"], callback_url=url)
        with pytest.raises(ProviderOAuthError):
            await oauth.complete_sign_in(session, uuid.uuid4(), state=flow["flow_id"], code="wrong-provider")
    assert oauth.sign_in_status(provider_id, flow["flow_id"])["status"] == "pending"


async def test_expired_replaced_cancelled_restart_and_occupied_ports(database, monkeypatch):
    factory, provider_id = await connected(database)

    def occupied(*_):
        raise RuntimeError("busy")

    monkeypatch.setattr(oauth, "register_callback", occupied)
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        first = oauth.start_sign_in(provider, "http://localhost:5173")
        second = oauth.start_sign_in(provider, "http://localhost:5173")
        assert first["callback_warning"] and second["manual_recovery"] == "paste_callback_url"
        assert oauth.sign_in_status(provider_id, first["flow_id"])["status"] == "expired"
        await cancel_sign_in(provider_id=provider_id, db=session)
        assert oauth.sign_in_status(provider_id, second["flow_id"])["status"] == "expired"
        assert provider.status == "connected"
        third = oauth.start_sign_in(provider, "http://localhost:5173")
        oauth._attempts[oauth._hash(third["flow_id"])].created_at -= 601
        assert oauth.sign_in_status(provider_id, third["flow_id"])["status"] == "expired"
        fourth = oauth.start_sign_in(provider, "http://localhost:5173")
        oauth._attempts.clear()
        assert oauth.sign_in_status(provider_id, fourth["flow_id"])["status"] == "expired"


@pytest.mark.parametrize("missing", ["access_token", "refresh_token", "expires_in", "account"])
async def test_failed_replacement_preserves_old_account(database, monkeypatch, missing):
    factory, provider_id = await connected(database)
    payload = grant("account-two", "second-refresh")
    if missing == "account":
        payload["access_token"] = "opaque-with-no-identity"
    else:
        payload.pop(missing)

    async def exchange(_):
        return payload

    monkeypatch.setattr(oauth, "token_request", exchange)
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        flow = oauth.start_sign_in(provider, "http://localhost:5173")
        with pytest.raises(ProviderOAuthError):
            await oauth.complete_sign_in(session, provider_id, state=flow["flow_id"], code="code")
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        assert provider.config["chatgpt_account_id"] == "account-one"
        assert reveal_provider_secret(provider.config["refresh_token"]) == "synthetic-refresh"
    assert oauth.sign_in_status(provider_id, flow["flow_id"])["status"] == "error"


async def test_refresh_is_coordinated_durable_and_keeps_pending(database, monkeypatch):
    factory, provider_id = await connected(database)
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        provider.config = {**provider.config, "oauth_expires_at": 1}
        await session.commit()
        flow = oauth.start_sign_in(provider, "http://localhost:5173")
    calls = []

    async def exchange(form):
        calls.append(form)
        await asyncio.sleep(0.02)
        return grant(refresh="rotated-refresh")

    monkeypatch.setattr(oauth, "token_request", exchange)

    async def resolve():
        async with factory() as session:
            provider = await session.get(ModelProvider, provider_id)
            result = await oauth.resolve_credential(session, provider)
            provider.name = "Uncommitted unrelated edit"
            await session.rollback()
            return result

    assert await asyncio.gather(resolve(), resolve()) == [token(), token()]
    assert len(calls) == 1
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        assert reveal_provider_secret(provider.config["refresh_token"]) == "rotated-refresh"
        assert provider.name == "Synthetic ChatGPT"
    assert oauth.sign_in_status(provider_id, flow["flow_id"])["status"] == "pending"


@pytest.mark.parametrize("terminal", [False, True])
async def test_refresh_failure_retains_credentials_and_marks_reconnect(database, monkeypatch, terminal):
    factory, provider_id = await connected(database)
    calls = []

    async def exchange(_):
        calls.append(True)
        error = ProviderOAuthError("safe failure")
        error.reconnect_required = terminal
        raise error

    monkeypatch.setattr(oauth, "token_request", exchange)
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        provider.config = {**provider.config, "oauth_expires_at": 1}
        await session.commit()
        for _ in range(2):
            with pytest.raises(ProviderOAuthError):
                await oauth.resolve_credential(session, provider)
    assert len(calls) == (1 if terminal else 2)
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        assert reveal_provider_secret(provider.config["refresh_token"]) == "synthetic-refresh"


async def test_disconnect_defeats_stale_generation_and_pending(database):
    factory, provider_id = await connected(database)
    async with factory() as caller, factory() as management:
        stale = await caller.get(ModelProvider, provider_id)
        flow = oauth.start_sign_in(stale, "http://localhost:5173")
        await disconnect_oauth(provider_id=provider_id, db=management)
        with pytest.raises(ProviderOAuthError, match="disconnected"):
            await oauth.resolve_credential(caller, stale)
        assert oauth.sign_in_status(provider_id, flow["flow_id"])["status"] == "expired"
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        assert not oauth.GRANT_KEYS.intersection(provider.config)
        assert provider.config["models"] == ["test-model"]


async def test_settings_cannot_inject_or_replay_stale_credentials(database):
    factory, provider_id = await connected(database)
    async with factory() as session:
        result = await update_provider(
            provider_id=provider_id,
            svc=ModelProviderService(session),
            body=ModelProviderUpdate(config={"access_token": "injected", "models": ["another-model"]}),
        )
        provider = await session.get(ModelProvider, provider_id)
        assert reveal_provider_secret(provider.config["access_token"]) == token()
        assert provider.config["models"] == ["another-model"]
        assert result.data.status == "connected"


async def test_usage_check_refreshes_401_once_and_never_generates(database, monkeypatch):
    factory, provider_id = await connected(database)
    requests = []
    original_client = httpx.AsyncClient

    def handler(request):
        requests.append(request)
        assert str(request.url) == oauth.USAGE_URL
        assert request.method == "GET"
        assert request.headers["ChatGPT-Account-ID"] == "account-one"
        return httpx.Response(401 if len(requests) == 1 else 200, json={"rate_limit": {"limit_reached": True}})

    async def exchange(_):
        return grant(refresh="rotated")

    monkeypatch.setattr(oauth, "token_request", exchange)
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs)
    )
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        result = await oauth.verify_connection(session, provider)
    assert result["status"] == "ok" and result["generation_tested"] is False
    assert "limit reached" in result["note"] and len(requests) == 2


def test_callback_log_redaction():
    record = logging.LogRecord(
        "uvicorn.access",
        20,
        "",
        0,
        "%s %s %s %s %s",
        ("localhost", "GET", "/api/v1/model-providers/oauth/callback/chatgpt/id?code=secret&state=secret", "1.1", 200),
        None,
    )
    OAuthCallbackLogFilter().filter(record)
    assert "secret" not in record.getMessage()


def test_payload_preserves_roles_images_tools_reasoning():
    result = responses_payload(
        {
            "model": "selected",
            "reasoning_effort": "high",
            "messages": [
                {"role": "system", "content": "Instruction"},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Inspect"},
                        {"type": "image_url", "image_url": {"url": "data:image/png;base64,synthetic"}},
                    ],
                },
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": "call-one", "function": {"name": "read", "arguments": "{}"}}],
                },
                {"role": "tool", "tool_call_id": "call-one", "content": "result"},
            ],
            "tools": [{"type": "function", "function": {"name": "read", "parameters": {"type": "object"}}}],
            "tool_choice": {"type": "function", "function": {"name": "read"}},
            "temperature": 0.3,
        }
    )
    assert result["input"][0]["content"][1]["type"] == "input_image"
    assert result["input"][1]["type"] == "function_call"
    assert result["input"][2]["type"] == "function_call_output"
    assert result["reasoning"] == {"effort": "high"}
    assert "temperature" not in result and result["store"] is False


async def test_stream_and_completion_use_only_subscription_backend(monkeypatch):
    original_client = httpx.AsyncClient
    events = [
        {"type": "response.output_text.delta", "delta": "hello"},
        {
            "type": "response.output_item.added",
            "output_index": 1,
            "item": {"type": "function_call", "call_id": "call-one", "name": "read"},
        },
        {"type": "response.function_call_arguments.delta", "output_index": 1, "delta": "{}"},
        {
            "type": "response.completed",
            "response": {"usage": {"input_tokens": 3, "output_tokens": 2, "total_tokens": 5}},
        },
    ]

    def handler(request):
        assert str(request.url) == oauth.RESPONSES_URL
        body = json.loads(request.content)
        assert body["model"] == "selected" and body["stream"] is True
        return httpx.Response(200, text="\n\n".join("data: " + json.dumps(event) for event in events))

    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original_client(transport=httpx.MockTransport(handler), **kwargs)
    )
    kwargs = {
        "auth_type": "oauth",
        "base_url": "https://ignored.example",
        "headers": {"Authorization": "Bearer synthetic", "ChatGPT-Account-ID": "account-one"},
        "payload": {"model": "selected", "messages": [{"role": "user", "content": "test"}]},
        "timeout": 1,
    }
    result = await model_chat_completion(**kwargs)
    assert result.json()["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] == "{}"
    assert result.json()["usage"]["total_tokens"] == 5
    async with model_chat_stream(**kwargs) as response:
        chunks = [line async for line in response.aiter_lines()]
    assert chunks[-1] == "data: [DONE]" and '"hello"' in chunks[0]


async def test_callback_authority_is_limited_to_loopback_and_management_requires_admin(database, monkeypatch):
    from fastapi import FastAPI

    from shogun.api.control_plane_auth import enforce_control_plane_access
    from shogun.api.deps import get_db
    from shogun.api.infrastructure_auth import INFRASTRUCTURE_TOKEN_HEADER
    from shogun.api.model_providers import provider_router

    factory, provider_id = database
    monkeypatch.setattr(oauth.settings, "infrastructure_admin_token", "synthetic-admin")

    async def exchange(_):
        return grant()

    monkeypatch.setattr(oauth, "token_request", exchange)

    async def db_override():
        async with factory() as session:
            yield session

    app = FastAPI()
    app.include_router(provider_router, prefix="/api/v1")
    app.dependency_overrides[get_db] = db_override
    app.middleware("http")(enforce_control_plane_access)
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        flow = oauth.start_sign_in(provider, "http://localhost:5173")
    path = f"/api/v1/model-providers/oauth/callback/chatgpt/{provider_id}"
    query = {"state": flow["flow_id"], "code": "synthetic-code"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("10.0.0.2", 1000)), base_url="http://localhost"
    ) as client:
        assert (await client.get(path, params=query)).status_code == 401
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 1000)), base_url="http://localhost"
    ) as client:
        assert (await client.post(f"/api/v1/model-providers/{provider_id}/oauth/cancel")).status_code == 401
        duplicate = await client.get(path + "?" + urlencode(query) + "&code=duplicate")
        assert duplicate.status_code == 422
        assert oauth.sign_in_status(provider_id, flow["flow_id"])["status"] == "pending"
        response = await client.get(path, params=query)
        assert response.status_code == 303
        assert "code=" not in response.headers["location"] and "state=" not in response.headers["location"]
        assert response.headers["cache-control"] == "no-store"
        result = await client.get(response.headers["location"])
        assert result.status_code == 200 and "connected" in result.text
        managed = await client.post(
            f"/api/v1/model-providers/{provider_id}/oauth/cancel",
            headers={INFRASTRUCTURE_TOKEN_HEADER: "synthetic-admin"},
        )
        assert managed.status_code == 200


async def test_switching_auth_removes_subscription_grants(database):
    factory, provider_id = await connected(database)
    async with factory() as session:
        await update_provider(
            provider_id=provider_id,
            svc=ModelProviderService(session),
            body=ModelProviderUpdate(auth_type="api_key", config={"api_key": "new-platform-key"}),
        )
        provider = await session.get(ModelProvider, provider_id)
        assert not oauth.GRANT_KEYS.intersection(provider.config)
        assert reveal_provider_secret(provider.config["api_key"]) == "new-platform-key"
        assert provider.base_url == "https://api.openai.com/v1"


@pytest.mark.parametrize(
    "events",
    [
        [{"type": "response.output_text.delta", "delta": "partial"}],
        [{"type": "response.failed", "response": {"error": {"message": "sensitive upstream payload"}}}],
        [{"type": "response.incomplete"}],
    ],
)
async def test_truncated_and_failed_streams_never_report_success(monkeypatch, events):
    original = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda _: httpx.Response(200, text="\n\n".join("data: " + json.dumps(event) for event in events))
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs))
    with pytest.raises(ProviderOAuthError) as error:
        await model_chat_completion(
            auth_type="oauth",
            base_url=oauth.RESPONSES_URL,
            headers={"Authorization": "Bearer synthetic", "ChatGPT-Account-ID": "account"},
            payload={"model": "test", "messages": []},
            timeout=1,
        )
    assert "sensitive upstream payload" not in str(error.value)


async def test_execution_routing_refreshes_before_registry_and_audit_writes(database, monkeypatch):
    from shogun.engine.flow_engine import _resolve_task_llm_chain
    from shogun.services.model_router import ModelRoutingService

    factory, provider_id = await connected(database)
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        provider.config = {**provider.config, "oauth_expires_at": 1, "models": ["gpt-5"]}
        await session.commit()
    calls = []

    async def exchange(_):
        calls.append(True)
        return grant(refresh="routing-rotation")

    async def no_audit(*_args, **_kwargs):
        pass

    monkeypatch.setattr(oauth, "token_request", exchange)
    monkeypatch.setattr(ModelRoutingService, "_audit", no_audit)
    async with factory() as session:
        chain, routing = await asyncio.wait_for(
            _resolve_task_llm_chain(session, prompt="Hello", required_capabilities=["chat"]), timeout=10
        )
        assert chain[0][0].id == provider_id
        assert chain[0][3]["ChatGPT-Account-ID"] == "account-one"
        assert routing["selected_model"] == "gpt-5"
        await session.rollback()
    async with factory() as session:
        provider = await session.get(ModelProvider, provider_id)
        assert reveal_provider_secret(provider.config["refresh_token"]) == "routing-rotation"
    assert len(calls) == 1
