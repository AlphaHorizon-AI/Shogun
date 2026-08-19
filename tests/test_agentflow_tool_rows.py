from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

from shogun.engine import flow_engine


def test_flow_artifact_manifest_distinguishes_reference_template_from_runtime_input():
    template_node = SimpleNamespace(
        id="template-node",
        label="Reference layout",
        node_type="file_template",
        config={},
    )
    source_node = SimpleNamespace(
        id="source-node",
        label="Source PDF",
        node_type="office",
        config={"action": "pdf_read", "input_path": "Input/source.pdf"},
    )

    template = flow_engine._flow_artifact_descriptor(
        template_node,
        {
            "__shogun_file_template__": True,
            "format": "xlsx",
            "template_path": "Input/example.xlsx",
        },
    )
    source = flow_engine._flow_artifact_descriptor(source_node, "runtime business data")

    assert (template["role"], template["kind"]) == ("template", "xlsx")
    assert (source["role"], source["kind"]) == ("input", "pdf")


def test_downstream_output_contract_declares_format_without_granting_write_tool():
    output = SimpleNamespace(
        label="Create result",
        node_type="office",
        config={
            "action": "excel_create",
            "sheet_name": "Data",
            "start_range": "A2",
            "output_filename": "result.xlsx",
        },
    )

    contracts = flow_engine._downstream_output_contracts(
        "samurai-node",
        {"samurai-node": [("output-node", None)]},
        {"output-node": output},
    )

    assert contracts == [{
        "node_id": "output-node",
        "label": "Create result",
        "node_type": "office",
        "action": "excel_create",
        "format": "xlsx",
        "sheet_name": "Data",
        "start_range": "A2",
        "output_path": "",
        "output_filename": "result.xlsx",
    }]


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


@pytest.mark.asyncio
async def test_native_semantic_failure_uses_shogun_text_adapter(monkeypatch):
    _FakeAsyncClient.responses = [
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "I extracted the requested records."}}]},
        ),
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '<tool_call>{"tool":"agentflow_submit_rows","arguments":'
                                '{"rows":[["A","B"],["C","D"]]}}</tool_call>'
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
        "gemma4:e4b",
        "http://localhost:11434/v1",
        {},
        profile={"mode": "native", "fallback_enabled": True},
        expected_width=2,
        timeout=10,
        max_tokens=1000,
        temperature=0,
        seed=None,
    )

    assert rows == [["A", "B"], ["C", "D"]]
    assert mode == "text"
    assert "tools" in _FakeAsyncClient.requests[0]
    assert "tools" not in _FakeAsyncClient.requests[1]
    assert "SHOGUN STRUCTURED TOOL PROTOCOL" in _FakeAsyncClient.requests[1]["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_native_empty_rows_use_text_adapter_before_chunk_recovery(monkeypatch):
    _FakeAsyncClient.responses = [
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "id": "call-empty",
                                    "type": "function",
                                    "function": {
                                        "name": "agentflow_submit_rows",
                                        "arguments": json.dumps({"rows": []}),
                                    },
                                }
                            ]
                        }
                    }
                ]
            },
        ),
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

    def require_one_row(rows):
        if not rows:
            raise flow_engine.IncompleteMatrixOutputError("This source requires one row")

    rows, _, mode = await flow_engine._call_llm_rows(
        [{"role": "user", "content": "Extract the required row"}],
        "gemma4:12b",
        "http://localhost:11434/v1",
        {},
        profile={"mode": "native", "fallback_enabled": True},
        expected_width=2,
        timeout=10,
        max_tokens=1000,
        temperature=0,
        seed=None,
        row_validator=require_one_row,
    )

    assert rows == [["A", "B"]]
    assert mode == "text"
    assert len(_FakeAsyncClient.requests) == 2
    assert "tools" in _FakeAsyncClient.requests[0]
    assert "tools" not in _FakeAsyncClient.requests[1]


@pytest.mark.asyncio
async def test_structured_coverage_failure_skips_identical_model_retries(monkeypatch):
    empty_native = httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call-empty",
                                "type": "function",
                                "function": {
                                    "name": "agentflow_submit_rows",
                                    "arguments": json.dumps({"rows": []}),
                                },
                            }
                        ]
                    }
                }
            ]
        },
    )
    empty_text = httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": (
                            '<tool_call>{"tool":"agentflow_submit_rows","arguments":'
                            '{"rows":[]}}</tool_call>'
                        )
                    }
                }
            ]
        },
    )
    _FakeAsyncClient.responses = [empty_native, empty_text]
    monkeypatch.setattr(flow_engine.httpx, "AsyncClient", _FakeAsyncClient)

    async def record_usage(*_args, **_kwargs):
        return None

    monkeypatch.setattr(flow_engine, "_record_model_usage", record_usage)
    provider = SimpleNamespace(id="provider-1", name="Local Ollama", provider_type="ollama")
    route_key = f"{provider.id}:gemma4:12b"

    def require_one_row(rows):
        if not rows:
            raise flow_engine.IncompleteMatrixOutputError("This source requires one row")

    with pytest.raises(flow_engine.ModelCallError) as captured:
        await flow_engine._call_llm_chain_rows(
            [{"role": "user", "content": "Extract the required row"}],
            [(provider, "gemma4:12b", "http://localhost:11434/v1", {})],
            timeout=10,
            retry_count=5,
            context="AgentFlow Samurai test chunk",
            expected_width=2,
            max_tokens=1000,
            routing_context={
                "tool_calling_profiles": {
                    route_key: {"mode": "native", "fallback_enabled": True},
                }
            },
            row_validator=require_one_row,
        )

    assert captured.value.cause_type == "IncompleteMatrixOutputError"
    assert len(_FakeAsyncClient.requests) == 2


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


@pytest.mark.asyncio
async def test_text_adapter_accepts_exact_width_markdown_table(monkeypatch):
    _FakeAsyncClient.responses = [
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "| A | B |\n|---|---|\n| C | D |"}}]},
        )
    ]
    monkeypatch.setattr(flow_engine.httpx, "AsyncClient", _FakeAsyncClient)

    rows, _, _ = await flow_engine._call_llm_rows(
        [{"role": "user", "content": "Extract the rows"}],
        "text-adapter",
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


@pytest.mark.asyncio
async def test_text_adapter_rejects_prose_instead_of_wrapping_it_as_a_row(monkeypatch):
    _FakeAsyncClient.responses = [
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "I extracted a useful summary."}}]},
        )
    ]
    monkeypatch.setattr(flow_engine.httpx, "AsyncClient", _FakeAsyncClient)

    with pytest.raises(ValueError, match="did not submit rows"):
        await flow_engine._call_llm_rows(
            [{"role": "user", "content": "Extract the rows"}],
            "text-adapter",
            "http://localhost:11434/v1",
            {},
            profile={"mode": "text", "fallback_enabled": True},
            expected_width=2,
            timeout=10,
            max_tokens=1000,
            temperature=0,
            seed=None,
        )


@pytest.mark.asyncio
async def test_row_coverage_validation_falls_back_to_next_model(monkeypatch):
    calls: list[str] = []

    async def call_rows(messages, model_name, base_url, headers, **kwargs):
        calls.append(model_name)
        if model_name == "primary-model":
            return [], "[]", "text"
        return [["TEST-A", "TEST-B"]], '[["TEST-A","TEST-B"]]', "text"

    def require_one_row(rows):
        if not rows:
            raise flow_engine.IncompleteMatrixOutputError(
                "This source requires at least 1 output row."
            )

    monkeypatch.setattr(flow_engine, "_call_llm_rows", call_rows)
    providers = [
        SimpleNamespace(id="provider-1", name="Primary", provider_type="openai"),
        SimpleNamespace(id="provider-2", name="Fallback", provider_type="openai"),
    ]

    rows = await flow_engine._call_llm_chain_rows(
        [{"role": "user", "content": "Extract one required record"}],
        [
            (providers[0], "primary-model", "https://primary.invalid/v1", {}),
            (providers[1], "fallback-model", "https://fallback.invalid/v1", {}),
        ],
        timeout=10,
        retry_count=0,
        context="AgentFlow Samurai test",
        expected_width=2,
        max_tokens=1000,
        routing_context=None,
        row_validator=require_one_row,
    )

    assert calls == ["primary-model", "fallback-model"]
    assert rows == [["TEST-A", "TEST-B"]]
