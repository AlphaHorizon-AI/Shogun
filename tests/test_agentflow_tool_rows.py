from __future__ import annotations

import json

import httpx
import pytest

from shogun.engine import flow_engine


class _FakeAsyncClient:
    requests: list[dict] = []
    responses: list[httpx.Response] = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, headers, json):
        self.requests.append(json)
        response = self.responses.pop(0)
        response.request = httpx.Request("POST", url)
        return response


@pytest.fixture(autouse=True)
def _reset_fake_client():
    _FakeAsyncClient.requests = []
    _FakeAsyncClient.responses = []


@pytest.mark.asyncio
async def test_native_agentflow_tool_returns_validated_two_dimensional_rows(monkeypatch):
    _FakeAsyncClient.responses = [
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "agentflow_submit_rows",
                                        "arguments": json.dumps(
                                            {"rows": [["TEST-A", "TEST-B", "TEST-C"], ["TEST-D", "TEST-E", "TEST-F"]]}
                                        ),
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
        )
    ]
    monkeypatch.setattr(flow_engine.httpx, "AsyncClient", _FakeAsyncClient)

    rows, _, mode = await flow_engine._call_llm_rows(
        [{"role": "user", "content": "Extract the rows"}],
        "gemma4:12b",
        "http://localhost:11434/v1",
        {},
        profile={"mode": "native", "fallback_enabled": True},
        expected_width=3,
        timeout=10,
        max_tokens=1000,
        temperature=0,
        seed=7,
    )

    assert rows == [["TEST-A", "TEST-B", "TEST-C"], ["TEST-D", "TEST-E", "TEST-F"]]
    assert mode == "native"
    request = _FakeAsyncClient.requests[0]
    assert request["tools"][0]["function"]["name"] == "agentflow_submit_rows"
    assert request["tool_choice"]["function"]["name"] == "agentflow_submit_rows"


@pytest.mark.asyncio
async def test_native_rejection_uses_shogun_text_adapter(monkeypatch):
    _FakeAsyncClient.responses = [
        httpx.Response(400, text="tools are unsupported"),
        httpx.Response(400, text="tools are unsupported"),
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '<tool_call>{"tool":"agentflow_submit_rows","arguments":'
                                '{"rows":[["A","B"]]}}</tool_call>'
                            )
                        }
                    }
                ]
            },
        ),
    ]
    monkeypatch.setattr(flow_engine.httpx, "AsyncClient", _FakeAsyncClient)

    rows, _, mode = await flow_engine._call_llm_rows(
        [{"role": "user", "content": "Extract the rows"}],
        "legacy-model",
        "http://localhost:11434/v1",
        {},
        profile={"mode": "native", "fallback_enabled": True},
        expected_width=2,
        timeout=10,
        max_tokens=1000,
        temperature=0,
        seed=None,
    )

    assert rows == [["A", "B"]]
    assert mode == "text"
    assert "tools" in _FakeAsyncClient.requests[0]
    assert "tools" in _FakeAsyncClient.requests[1]
    assert "tool_choice" not in _FakeAsyncClient.requests[1]
    assert "tools" not in _FakeAsyncClient.requests[2]
    assert "SHOGUN STRUCTURED TOOL PROTOCOL" in _FakeAsyncClient.requests[2]["messages"][-1]["content"]


def test_agentflow_tool_rejects_wrong_destination_width():
    with pytest.raises(ValueError, match="exactly 3 values"):
        flow_engine._validate_agentflow_rows({"rows": [["A", "B"]]}, 3)


@pytest.mark.asyncio
async def test_text_adapter_accepts_strict_legacy_json_matrix(monkeypatch):
    _FakeAsyncClient.responses = [
        httpx.Response(200, json={"choices": [{"message": {"content": '[["A","B"],["C","D"]]'}}]})
    ]
    monkeypatch.setattr(flow_engine.httpx, "AsyncClient", _FakeAsyncClient)

    rows, _, mode = await flow_engine._call_llm_rows(
        [{"role": "user", "content": "Extract the rows"}],
        "gemma3:12b",
        "http://localhost:11434/v1",
        {},
        profile={"mode": "text", "fallback_enabled": True},
        expected_width=2,
        timeout=10,
        max_tokens=1000,
        temperature=0,
        seed=None,
    )

    assert rows == [["A", "B"], ["C", "D"]]
    assert mode == "text"
