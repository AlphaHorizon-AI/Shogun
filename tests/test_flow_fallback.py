from __future__ import annotations

import uuid
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.db.models.model_routing import ModelRoutingProfile
from shogun.engine import flow_engine
from shogun.services import notification_service, posture_guard
from shogun.services.model_service import ModelRoutingProfileService


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_provider_connection_resolves_protected_api_key(monkeypatch):
    provider = SimpleNamespace(
        config={"api_key": "enc:protected-value", "model": "test-model"},
        base_url="https://openrouter.ai/api/v1",
        provider_type="openrouter",
        name="OpenRouter",
    )
    seen_configs: list[dict] = []

    def resolve_api_key(config):
        seen_configs.append(config)
        return "decrypted-api-key"

    monkeypatch.setattr(flow_engine, "provider_api_key", resolve_api_key)

    _, model, _, headers = flow_engine._provider_connection(provider)

    assert seen_configs == [provider.config]
    assert model == "test-model"
    assert headers["Authorization"] == "Bearer decrypted-api-key"


def test_provider_connection_accepts_bearer_token_credentials():
    provider = SimpleNamespace(
        config={"access_token": "provider-access-token", "model": "test-model"},
        base_url="https://provider.invalid/v1",
        provider_type="custom",
        name="Token Provider",
    )

    _, _, _, headers = flow_engine._provider_connection(provider)

    assert headers["Authorization"] == "Bearer provider-access-token"


def test_exhausted_retry_policy_is_terminal():
    actions = {
        name: flow_engine._node_failure_action(config)
        for name, config in {
            "retry": {"failure_action": "retry"},
            "stop": {"failure_action": "stop"},
            "legacy_stop": {"on_failure": "fail_parent"},
            "continue": {"failure_action": "continue"},
            "skip": {"failure_action": "skip"},
        }.items()
    }

    assert flow_engine._failure_action_is_terminal(actions["retry"]) is True
    assert flow_engine._failure_action_is_terminal(actions["stop"]) is True
    assert flow_engine._failure_action_is_terminal(actions["legacy_stop"]) is True
    assert flow_engine._failure_action_is_terminal(actions["continue"]) is False
    assert flow_engine._failure_action_is_terminal(actions["skip"]) is False


@pytest.mark.asyncio
async def test_samurai_falls_back_after_timeout(monkeypatch):
    calls: list[tuple[str, int]] = []
    fallback_events: list[dict] = []

    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())

    async def resolve_chain(_session, _profile_id=None):
        return [
            (object(), "primary-model", "https://primary.invalid/v1", {}),
            (object(), "fallback-model", "https://fallback.invalid/v1", {}),
        ]

    async def call_llm(_messages, model_name, _base_url, _headers, timeout):
        calls.append((model_name, timeout))
        if model_name == "primary-model":
            raise httpx.ReadTimeout("primary timed out")
        return "fallback response"

    async def notify(**kwargs):
        fallback_events.append(kwargs)

    monkeypatch.setattr(flow_engine, "_resolve_llm_chain", resolve_chain)
    monkeypatch.setattr(flow_engine, "_call_llm", call_llm)
    monkeypatch.setattr(notification_service, "notify_model_fallback", notify)

    result = await flow_engine._exec_samurai(
        {"task_description": "Do the work", "timeout": 7, "retry_count": 0},
        "",
    )

    assert result == "fallback response"
    assert calls == [("primary-model", 7), ("fallback-model", 7)]
    assert fallback_events[0]["from_model"] == "primary-model"
    assert fallback_events[0]["to_model"] == "fallback-model"
    assert fallback_events[0]["reason"] == "timeout after 7s"


@pytest.mark.asyncio
async def test_samurai_exhausts_retries_before_fallback(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())

    async def resolve_chain(_session, _profile_id=None):
        return [
            (object(), "primary", "https://primary.invalid/v1", {}),
            (object(), "fallback", "https://fallback.invalid/v1", {}),
        ]

    async def call_llm(_messages, model_name, _base_url, _headers, _timeout):
        calls.append(model_name)
        if model_name == "primary":
            raise ValueError("provider unavailable")
        return "ok"

    async def notify(**_kwargs):
        return None

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(flow_engine, "_resolve_llm_chain", resolve_chain)
    monkeypatch.setattr(flow_engine, "_call_llm", call_llm)
    monkeypatch.setattr(notification_service, "notify_model_fallback", notify)
    monkeypatch.setattr(flow_engine.asyncio, "sleep", no_sleep)

    assert await flow_engine._exec_samurai(
        {"task_description": "Do the work", "timeout": 12, "retry_count": 1},
        "",
    ) == "ok"
    assert calls == ["primary", "primary", "fallback"]


@pytest.mark.asyncio
async def test_exhausted_timeout_has_actionable_route_and_context_details(monkeypatch):
    provider = SimpleNamespace(name="Local Ollama", provider_type="ollama")

    async def call_llm(*_args, **_kwargs):
        raise httpx.ReadTimeout("")

    async def record_usage(*_args, **_kwargs):
        return None

    monkeypatch.setattr(flow_engine, "_call_llm", call_llm)
    monkeypatch.setattr(flow_engine, "_record_model_usage", record_usage)

    with pytest.raises(flow_engine.ModelCallError) as captured:
        await flow_engine._call_llm_chain(
            [{"role": "user", "content": "spreadsheet rows"}],
            [(provider, "qwen-test", "http://localhost:11434/v1", {})],
            timeout=120,
            retry_count=0,
            context="AgentFlow Samurai node",
        )

    error = captured.value
    assert str(error) == "AgentFlow Samurai node timed out after 120s using Local Ollama/qwen-test"
    assert error.cause_type == "ReadTimeout"
    assert error.provider == "Local Ollama"
    assert error.model == "qwen-test"
    assert error.input_characters > len("spreadsheet rows")
    assert error.estimated_input_tokens > 0


@pytest.mark.asyncio
async def test_channel_node_injects_predecessor_context(monkeypatch):
    delivered: list[dict] = []

    async def send(message, **kwargs):
        delivered.append({"message": message, **kwargs})
        return {"telegram": {"ok": True, "sent": 1}}

    monkeypatch.setattr(notification_service, "send_channel_message", send)

    result = await flow_engine._exec_channel_send(
        {
            "channel": "telegram",
            "message_template": "Workflow completed:\n{{context}}",
            "telegram_chat_ids": ["123"],
            "message_thread_id": 22,
        },
        "final report",
    )

    assert result == "Message delivered via telegram"
    assert delivered[0]["message"] == "Workflow completed:\nfinal report"
    assert delivered[0]["telegram_chat_ids"] == ["123"]
    assert delivered[0]["telegram_message_thread_id"] == 22


def test_active_skill_context_is_limited_to_model_consumers():
    assert flow_engine._node_uses_active_skill_context("samurai", {}) is True
    assert flow_engine._node_uses_active_skill_context("coding", {"action": "analyze"}) is True
    assert flow_engine._node_uses_active_skill_context("coding", {"action": "write_file"}) is False
    assert flow_engine._node_uses_active_skill_context("mado_browser", {}) is False
    assert flow_engine._node_uses_active_skill_context("email_send", {}) is False
    assert flow_engine._node_uses_active_skill_context("channel_send", {}) is False


@pytest.mark.asyncio
async def test_channel_execution_never_delivers_private_skill_context(monkeypatch):
    delivered: list[str] = []

    async def update_state(*_args, **_kwargs):
        return None

    async def send(message, **_kwargs):
        delivered.append(message)
        return {"telegram": {"ok": True, "sent": 1}}

    monkeypatch.setattr(flow_engine, "_update_node_state", update_state)
    monkeypatch.setattr(notification_service, "send_channel_message", send)

    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="channel_send",
        label="Send morning brief",
        config={"channel": "telegram", "message_template": "{{context}}"},
    )
    predecessor_id = str(uuid.uuid4())
    predecessor = SimpleNamespace(label="Compile AI News Brief")

    result = await flow_engine._execute_single_node(
        run_id=uuid.uuid4(),
        node=node,
        predecessor_outputs={predecessor_id: "The actual morning brief"},
        node_map={predecessor_id: predecessor},
    )

    assert result == "Message delivered via telegram"
    assert delivered == ["[Output from 'Compile AI News Brief']:\nThe actual morning brief"]
    assert "SKILL AWARENESS PROTOCOL" not in delivered[0]


@pytest.mark.asyncio
async def test_extract_node_with_url_navigates_before_reading(monkeypatch, tmp_path):
    from shogun.config import settings

    monkeypatch.setattr(settings, "mado_path", tmp_path / "mado")
    from shogun.services import mado_hardening, mado_service

    calls: list[tuple[str, str | None]] = []

    async def allowed(*_args, **_kwargs):
        return None

    async def posture():
        return {"active_tier": "campaign"}

    async def launched(**_kwargs):
        return {"status": "already_active"}

    async def governed(_session_id, _action_type, operation, **_kwargs):
        return await operation()

    async def navigate(*, session_id, url):
        calls.append(("navigate", url))
        return {"status": "ok", "url": url, "title": "AI News"}

    async def extract(*, session_id, selector, extract_type):
        calls.append(("extract", selector))
        return {"status": "ok", "content": "Headline one\nHeadline two"}

    monkeypatch.setattr(posture_guard, "check_mado_access", allowed)
    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", posture)
    monkeypatch.setattr(posture_guard, "check_mado_browser_mode", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mado_hardening.permission_guard, "check", allowed)
    monkeypatch.setattr(mado_hardening, "governed_action", governed)
    monkeypatch.setattr(mado_hardening.runtime_registry, "register", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mado_service, "launch_browser", launched)
    monkeypatch.setattr(mado_service, "navigate", navigate)
    monkeypatch.setattr(mado_service, "extract_content", extract)
    monkeypatch.setitem(mado_service._active_contexts, "flow_morning_news", object())

    result = await flow_engine._exec_mado_browser(
        {
            "action": "extract_content",
            "url": "https://example.test/ai",
            "selector": "article",
            "session_name": "morning_news",
        },
        "",
    )

    assert result == "Headline one\nHeadline two"
    assert calls == [("navigate", "https://example.test/ai"), ("extract", "article")]


def test_notification_cursor_only_returns_new_events():
    notification_service._notifications.clear()
    first = notification_service.publish_notification(
        event_type="model.fallback",
        title="Fallback",
        message="First",
    )
    second = notification_service.publish_notification(
        event_type="model.fallback",
        title="Fallback",
        message="Second",
    )

    assert notification_service.list_notifications(first["id"]) == [second]


@pytest.mark.asyncio
async def test_setting_default_routing_profile_clears_previous_default():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: ModelRoutingProfile.__table__.create(sync_connection)
        )

    async with sessions() as session:
        service = ModelRoutingProfileService(session)
        first = await service.create(name="First", rules=[], is_default=True)
        second = await service.create(name="Second", rules=[], is_default=False)
        await service.update(second.id, is_default=True)
        await session.commit()
        await session.refresh(first)
        await session.refresh(second)
        assert first.is_default is False
        assert second.is_default is True

    await engine.dispose()
