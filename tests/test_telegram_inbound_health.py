from __future__ import annotations

import httpx
import pytest

from shogun.services import channel_service
from shogun.services.channel_service import ChannelService
from shogun.services.telegram_poller import (
    _remove_stale_telegram_webhook,
    _telegram_message_is_allowed,
    _telegram_polling_conflict_kind,
)


def _response(status: int, payload: dict) -> httpx.Response:
    return httpx.Response(
        status,
        json=payload,
        request=httpx.Request("GET", "https://api.telegram.org/test"),
    )


def test_forum_message_can_be_authorized_by_group_or_operator_id():
    message = {
        "chat": {"id": -100123, "type": "supergroup"},
        "from": {"id": 456},
        "message_thread_id": 22,
        "text": "Hey Max",
    }

    assert _telegram_message_is_allowed(message, ["-100123"])
    assert _telegram_message_is_allowed(message, ["456"])
    assert not _telegram_message_is_allowed(message, ["999"])
    assert _telegram_message_is_allowed(message, [])


def test_polling_conflict_distinguishes_webhook_and_duplicate_instance():
    webhook = _response(
        409,
        {"description": "Conflict: can't use getUpdates method while webhook is active"},
    )
    duplicate = _response(
        409,
        {"description": "Conflict: terminated by other getUpdates request"},
    )

    assert _telegram_polling_conflict_kind(webhook) == "webhook"
    assert _telegram_polling_conflict_kind(duplicate) == "competing_poller"
    assert _telegram_polling_conflict_kind(_response(401, {})) is None


@pytest.mark.asyncio
async def test_stale_webhook_recovery_preserves_pending_updates():
    calls = []

    class Client:
        async def post(self, url, json):
            calls.append((url, json))
            return _response(200, {"ok": True, "result": True})

    assert await _remove_stale_telegram_webhook(Client(), "token") is True
    assert calls == [
        (
            "https://api.telegram.org/bottoken/deleteWebhook",
            {"drop_pending_updates": False},
        )
    ]


@pytest.mark.asyncio
async def test_polling_connect_removes_webhook_and_records_privacy_capability(monkeypatch):
    saved = []
    calls = []

    class Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url):
            calls.append(("get", url, None))
            return _response(
                200,
                {
                    "ok": True,
                    "result": {
                        "id": 42,
                        "username": "max_bot",
                        "first_name": "Max",
                        "can_join_groups": True,
                        "can_read_all_group_messages": False,
                    },
                },
            )

        async def post(self, url, json):
            calls.append(("post", url, json))
            return _response(200, {"ok": True, "result": True})

    async def get_settings():
        return {}

    async def save_settings(settings):
        saved.append(settings)

    monkeypatch.setattr(channel_service.httpx, "AsyncClient", Client)
    monkeypatch.setattr(channel_service, "_get_agent_bushido", get_settings)
    monkeypatch.setattr(channel_service, "_save_agent_bushido", save_settings)

    result = await ChannelService().connect_telegram(
        "token",
        mode="polling",
        allowed_chat_ids=["456"],
    )

    assert result["connected"] is True
    assert result["can_read_all_group_messages"] is False
    assert calls[1] == (
        "post",
        "https://api.telegram.org/bottoken/deleteWebhook",
        {"drop_pending_updates": False},
    )
    assert saved[0]["telegram_config"]["allowed_chat_ids"] == ["456"]
    assert "bot_token" not in result
