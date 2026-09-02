from __future__ import annotations

import asyncio

import pytest

from shogun.services import harakiri_runtime, notification_service, telegram_poller


@pytest.fixture(autouse=True)
def reset_runtime_latch():
    harakiri_runtime.reset_harakiri_latch()
    yield
    harakiri_runtime.reset_harakiri_latch()


@pytest.mark.asyncio
async def test_exact_telegram_harakiri_takes_emergency_path_and_acknowledges(monkeypatch):
    controls: list[tuple[str, str, str]] = []
    messages: list[dict] = []

    async def no_typing(*_args, **_kwargs):
        return None

    async def activate(action, *, source, actor):
        controls.append((action, source, actor))
        harakiri_runtime.engage_harakiri_latch()
        return {"kill_switch_active": True}

    async def send(_token, chat_id, text, **kwargs):
        messages.append({"chat_id": chat_id, "text": text, **kwargs})
        return 9

    monkeypatch.setattr(telegram_poller, "send_chat_action", no_typing)
    monkeypatch.setattr("shogun.services.harakiri_control.execute_harakiri_control", activate)
    monkeypatch.setattr(telegram_poller, "send_telegram_message", send)

    await telegram_poller._process_telegram_message("token", "42", " ++HaRaKiRi ")

    assert controls == [("activate", "telegram", "42")]
    assert len(messages) == 1
    assert "HARAKIRI ACTIVATED" in messages[0]["text"]
    assert messages[0]["allow_during_harakiri"] is True


@pytest.mark.asyncio
async def test_telegram_tasks_are_tracked_and_cancelled():
    started = asyncio.Event()
    stopped = asyncio.Event()

    async def runaway_response():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    task = telegram_poller.create_telegram_message_task(runaway_response())
    await started.wait()
    count = await telegram_poller.cancel_active_telegram_messages()

    assert count == 1
    assert task.cancelled()
    assert stopped.is_set()
    assert task not in telegram_poller._active_message_tasks


@pytest.mark.asyncio
async def test_harakiri_latch_blocks_late_telegram_output(monkeypatch):
    calls: list[dict] = []

    class Response:
        is_success = True
        text = ""

        @staticmethod
        def json():
            return {"result": {"message_id": 7}}

    class Client:
        async def post(self, _url, *, json):
            calls.append(json)
            return Response()

    monkeypatch.setattr(telegram_poller, "_get_tg_client", lambda: Client())
    harakiri_runtime.engage_harakiri_latch()

    blocked = await telegram_poller.send_telegram_message("token", "1", "stale output")
    acknowledgement = await telegram_poller.send_telegram_message(
        "token", "1", "HARAKIRI ACTIVATED", allow_during_harakiri=True
    )
    edited = await telegram_poller.edit_telegram_message("token", "1", 5, "stale edit")

    assert blocked is None
    assert edited is False
    assert acknowledgement == 7
    assert calls == [{"chat_id": "1", "text": "HARAKIRI ACTIVATED", "parse_mode": "Markdown"}]


@pytest.mark.asyncio
async def test_harakiri_blocks_native_outbound_channel_bypass(monkeypatch):
    calls: list[str] = []

    async def unexpected_telegram(*_args, **_kwargs):
        calls.append("telegram")
        return {"ok": True, "sent": 1}

    monkeypatch.setattr(notification_service, "_send_telegram", unexpected_telegram)
    harakiri_runtime.engage_harakiri_latch()

    result = await notification_service.send_channel_message("stale agent output", channel="both")

    assert calls == []
    assert result["telegram"]["blocked"] is True


@pytest.mark.asyncio
async def test_runtime_harakiri_cancels_runaway_telegram_task(monkeypatch):
    started = asyncio.Event()

    async def runaway_response():
        started.set()
        await asyncio.Event().wait()

    async def no_stacks(_reason):
        return 0

    task = telegram_poller.create_telegram_message_task(runaway_response())
    await started.wait()
    monkeypatch.setattr("shogun.services.stack_orchestrator.cancel_all_stack_runs", no_stacks)

    result = await harakiri_runtime.cancel_active_runtime()

    assert harakiri_runtime.harakiri_latch_active() is True
    assert result["telegram"] == 1
    assert task.cancelled()
