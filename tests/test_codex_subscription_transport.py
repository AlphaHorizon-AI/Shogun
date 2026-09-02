from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from shogun.services.codex_app_server import (
    _conversation_text,
    _tool_response_schema,
    parse_structured_tool_response,
)
from shogun.services.model_transport import model_chat_completion, model_chat_stream


def test_conversation_transport_preserves_role_order_and_tool_results() -> None:
    prompt = _conversation_text(
        [
            {"role": "system", "content": "Follow the operator policy."},
            {"role": "user", "content": "Look this up."},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "call_1", "function": {"name": "lookup"}}],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "verified result"},
        ],
        None,
    )

    conversation = json.loads(prompt.split("CONVERSATION_JSON:\n", 1)[1])
    assert [item["role"] for item in conversation] == ["system", "user", "assistant", "tool"]
    assert conversation[-1]["tool_call_id"] == "call_1"
    assert conversation[-1]["content"] == "verified result"


def test_forced_tool_schema_and_response_adapter() -> None:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "parameters": {"type": "object", "properties": {"query": {"type": "string"}}},
            },
        }
    ]
    schema = _tool_response_schema(
        tools,
        {"type": "function", "function": {"name": "lookup"}},
    )
    assert schema["properties"]["tool_calls"]["minItems"] == 1
    assert schema["properties"]["tool_calls"]["items"]["properties"]["name"]["enum"] == ["lookup"]

    content, calls = parse_structured_tool_response(
        '{"content":"","tool_calls":[{"name":"lookup","arguments":{"query":"Shogun"}}]}'
    )
    assert content == ""
    assert calls[0]["function"]["name"] == "lookup"
    assert json.loads(calls[0]["function"]["arguments"]) == {"query": "Shogun"}


@pytest.mark.asyncio
async def test_non_streaming_subscription_completion_is_openai_compatible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCodex:
        async def run_completion(self, _payload, *, timeout: float, stream: bool):
            assert timeout == 45.0
            assert stream is False
            yield {"type": "content", "content": "Subscription response"}

    monkeypatch.setattr(
        "shogun.services.model_transport.get_codex_app_server",
        lambda: FakeCodex(),
    )
    response = await model_chat_completion(
        auth_type="chatgpt",
        base_url="",
        headers={},
        payload={"model": "gpt-test", "messages": [{"role": "user", "content": "Hello"}]},
        timeout=45.0,
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["choices"][0]["message"]["content"] == "Subscription response"
    assert payload["model"] == "gpt-test"


@pytest.mark.asyncio
async def test_subscription_stream_reports_missing_sign_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeCodex:
        async def account(self, *, refresh: bool):
            assert refresh is False
            return {"account": None}

    monkeypatch.setattr(
        "shogun.services.model_transport.get_codex_app_server",
        lambda: FakeCodex(),
    )
    async with model_chat_stream(
        auth_type="chatgpt",
        base_url="",
        headers={},
        payload={"model": "gpt-test", "messages": []},
        timeout=30.0,
    ) as response:
        body = await response.aread()

    assert response.status_code == 401
    assert "not connected" in body.decode()


@pytest.mark.asyncio
async def test_subscription_stream_emits_openai_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeCodex:
        async def account(self, *, refresh: bool):
            return {"account": {"type": "chatgpt"}}

        async def run_completion(self, _payload, *, timeout: float, stream: bool):
            assert stream is True
            yield {"type": "content", "content": "Hello"}
            yield {"type": "content", "content": " world"}

    monkeypatch.setattr(
        "shogun.services.model_transport.get_codex_app_server",
        lambda: FakeCodex(),
    )
    async with model_chat_stream(
        auth_type="chatgpt",
        base_url="",
        headers={},
        payload={"model": "gpt-test", "messages": []},
        timeout=30.0,
    ) as response:
        lines = [line async for line in response.aiter_lines()]

    chunks = [json.loads(line.removeprefix("data: ")) for line in lines[:-1]]
    assert [chunk["choices"][0]["delta"]["content"] for chunk in chunks] == ["Hello", " world"]
    assert lines[-1] == "data: [DONE]"


@pytest.mark.asyncio
async def test_subscription_account_sync_uses_codex_model_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from shogun.api.model_providers import _sync_codex_provider

    class FakeCodex:
        async def account(self, *, refresh: bool):
            assert refresh is False
            return {"account": {"type": "chatgpt", "planType": "plus"}}

        async def list_models(self):
            return [{"model": "gpt-z"}, {"id": "gpt-a"}, {"model": "gpt-z"}]

    class FakeSession:
        flushed = False

        async def flush(self):
            self.flushed = True

    monkeypatch.setattr(
        "shogun.api.model_providers.get_codex_app_server",
        lambda: FakeCodex(),
    )
    provider = SimpleNamespace(
        config={},
        status="not_configured",
        health_status="unknown",
        base_url="https://api.openai.com/v1",
    )
    session = FakeSession()

    models = await _sync_codex_provider(session, provider)

    assert models == ["gpt-a", "gpt-z"]
    assert provider.config == {
        "codex_account_connected": True,
        "codex_plan_type": "plus",
        "models": ["gpt-a", "gpt-z"],
    }
    assert provider.status == "connected"
    assert provider.health_status == "healthy"
    assert provider.base_url is None
    assert session.flushed is True
