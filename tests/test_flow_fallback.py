from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.db.models.model_routing import ModelRoutingProfile
from shogun.engine import flow_engine
from shogun.services import notification_service
from shogun.services.model_service import ModelRoutingProfileService


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


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
