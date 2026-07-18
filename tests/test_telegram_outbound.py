from __future__ import annotations

import json

import pytest

from shogun.services import channel_service, notification_service
from shogun.services.native_skills import NATIVE_TOOLS, execute_native_tool
from shogun.services.tool_gate import TOOL_RISK_REGISTRY


def _telegram_tool() -> dict:
    return next(
        tool for tool in NATIVE_TOOLS
        if tool["function"]["name"] == "send_telegram_message"
    )


def test_send_telegram_message_schema_exposes_optional_topic_id():
    tool = _telegram_tool()
    parameters = tool["function"]["parameters"]

    assert parameters["required"] == ["chat_id", "text"]
    assert parameters["properties"]["chat_id"]["type"] == "integer"
    assert parameters["properties"]["message_thread_id"]["type"] == "integer"
    assert "message_thread_id" not in parameters["required"]
    assert TOOL_RISK_REGISTRY["send_telegram_message"]["risk"] == "high"


@pytest.mark.asyncio
async def test_native_tool_passes_topic_id_to_channel_sender(monkeypatch):
    delivered: list[dict] = []

    async def send(message, **kwargs):
        delivered.append({"message": message, **kwargs})
        return {"telegram": {"ok": True, "sent": 1, "errors": []}}

    monkeypatch.setattr(notification_service, "send_channel_message", send)

    result = json.loads(await execute_native_tool(
        "send_telegram_message",
        {"chat_id": -100123, "text": "Morning brief", "message_thread_id": 22},
        object(),
    ))

    assert result["status"] == "success"
    assert delivered == [{
        "message": "Morning brief",
        "channel": "telegram",
        "telegram_chat_ids": ["-100123"],
        "telegram_message_thread_id": 22,
    }]


@pytest.mark.asyncio
async def test_native_tool_without_topic_id_remains_backward_compatible(monkeypatch):
    delivered: list[dict] = []

    async def send(message, **kwargs):
        delivered.append({"message": message, **kwargs})
        return {"telegram": {"ok": True, "sent": 1, "errors": []}}

    monkeypatch.setattr(notification_service, "send_channel_message", send)

    result = json.loads(await execute_native_tool(
        "send_telegram_message",
        {"chat_id": -100123, "text": "General update"},
        object(),
    ))

    assert result["status"] == "success"
    assert delivered[0]["telegram_message_thread_id"] is None


def test_topic_helper_is_reusable_for_text_and_future_media_payloads():
    text_payload = notification_service._apply_telegram_message_thread(
        {"chat_id": "-100123", "text": "Hello"}, 22
    )
    photo_payload = notification_service._apply_telegram_message_thread(
        {"chat_id": "-100123", "photo": "file-id"}, 22
    )

    assert text_payload["message_thread_id"] == 22
    assert photo_payload["message_thread_id"] == 22


def test_topic_helper_omits_field_when_no_topic_is_requested():
    payload = notification_service._apply_telegram_message_thread(
        {"chat_id": "-100123", "text": "General"}, None
    )

    assert "message_thread_id" not in payload


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("message_thread_id", "expected_payload"),
    [
        (22, {"chat_id": "-100123", "text": "Brief", "message_thread_id": 22}),
        (None, {"chat_id": "-100123", "text": "Brief"}),
    ],
)
async def test_telegram_api_payload_includes_topic_only_when_requested(
    monkeypatch,
    message_thread_id,
    expected_payload,
):
    posts: list[dict] = []

    async def config():
        return {
            "telegram_config": {
                "connected": True,
                "bot_token": "test-token",
                "allowed_chat_ids": [],
            }
        }

    class Response:
        is_success = True
        status_code = 200

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, json):
            posts.append({"url": url, "json": json})
            return Response()

    monkeypatch.setattr(channel_service, "_get_agent_bushido", config)
    monkeypatch.setattr(notification_service.httpx, "AsyncClient", Client)

    result = await notification_service._send_telegram(
        "Brief",
        ["-100123"],
        message_thread_id=message_thread_id,
    )

    assert result["ok"] is True
    assert posts[0]["url"].endswith("/bottest-token/sendMessage")
    assert posts[0]["json"] == expected_payload
