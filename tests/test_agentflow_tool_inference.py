"""Unit test for Samurai node tool-augmented LLM inference and ToolGate evaluation."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shogun.engine import flow_engine
from shogun.services.tool_gate import GateAction, GateDecision, RiskLevel


@pytest.mark.asyncio
async def test_samurai_tool_calling_loop_executes_tool_and_returns_final_response():
    """Verify _call_llm_with_tools processes tool calls and executes them."""

    messages = [{"role": "user", "content": "Fetch the echo text."}]
    tools = [{
        "type": "function",
        "function": {
            "name": "echo_tool",
            "description": "Echo back text",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"]
            }
        }
    }]

    executed_calls = []

    async def mock_tool_executor(tool_name, args, session):
        executed_calls.append((tool_name, args))
        return f"Echoed: {args.get('text')}"

    # Response 1: Model requests echo_tool call
    response_1 = MagicMock()
    response_1.status_code = 200
    response_1.json.return_value = {
        "choices": [{
            "message": {
                "content": None,
                "tool_calls": [{
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "echo_tool",
                        "arguments": json.dumps({"text": "Hello Shogun"})
                    }
                }]
            }
        }]
    }

    # Response 2: Model returns final text output after receiving tool result
    response_2 = MagicMock()
    response_2.status_code = 200
    response_2.json.return_value = {
        "choices": [{
            "message": {
                "content": "The tool returned: Echoed: Hello Shogun",
                "tool_calls": []
            }
        }]
    }

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=[response_1, response_2])

    with patch("httpx.AsyncClient", return_value=mock_client), \
         patch("shogun.services.tool_gate.check_tool_access", new_callable=AsyncMock) as mock_gate:
        mock_gate.return_value = GateDecision(
            action=GateAction.ALLOW,
            reason="Tool allowed",
            risk_level=RiskLevel.LOW,
            tool_name="echo_tool"
        )

        result = await flow_engine._call_llm_with_tools(
            messages=messages,
            model_name="test-model",
            base_url="http://localhost:8000",
            headers={},
            tools=tools,
            tool_executor=mock_tool_executor,
            governance_context={"posture_level": "campaign"}
        )

    assert result == "The tool returned: Echoed: Hello Shogun"
    assert len(executed_calls) == 1
    assert executed_calls[0] == ("echo_tool", {"text": "Hello Shogun"})


@pytest.mark.asyncio
async def test_samurai_tool_calling_loop_blocks_when_toolgate_denies():
    """Verify ToolGate BLOCK action halts tool execution and passes status to LLM."""

    messages = [{"role": "user", "content": "Run dangerous tool."}]
    tools = [{
        "type": "function",
        "function": {
            "name": "restricted_tool",
            "description": "Restricted operation",
            "parameters": {"type": "object", "properties": {}}
        }
    }]

    executed_calls = []

    async def mock_tool_executor(tool_name, args, session):
        executed_calls.append((tool_name, args))
        return "Executed"

    response_1 = MagicMock()
    response_1.status_code = 200
    response_1.json.return_value = {
        "choices": [{
            "message": {
                "content": None,
                "tool_calls": [{
                    "id": "call_456",
                    "type": "function",
                    "function": {
                        "name": "restricted_tool",
                        "arguments": "{}"
                    }
                }]
            }
        }]
    }

    response_2 = MagicMock()
    response_2.status_code = 200
    response_2.json.return_value = {
        "choices": [{
            "message": {
                "content": "Operation was blocked by ToolGate policy.",
                "tool_calls": []
            }
        }]
    }

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=[response_1, response_2])

    with patch("httpx.AsyncClient", return_value=mock_client), \
         patch("shogun.services.tool_gate.check_tool_access", new_callable=AsyncMock) as mock_gate:
        mock_gate.return_value = GateDecision(
            action=GateAction.BLOCK,
            reason="Blocked by posture policy",
            risk_level=RiskLevel.HIGH,
            tool_name="restricted_tool"
        )

        result = await flow_engine._call_llm_with_tools(
            messages=messages,
            model_name="test-model",
            base_url="http://localhost:8000",
            headers={},
            tools=tools,
            tool_executor=mock_tool_executor,
            governance_context={"posture_level": "guarded"}
        )

    assert result == "Operation was blocked by ToolGate policy."
    assert len(executed_calls) == 0  # Tool was blocked, not executed!


@pytest.mark.asyncio
@pytest.mark.parametrize("gate_outcome", [GateAction.CONFIRM, RuntimeError("gate unavailable")])
async def test_samurai_tool_loop_never_executes_without_an_allow_decision(gate_outcome):
    tools = [{
        "type": "function",
        "function": {
            "name": "read_tool",
            "description": "Read test data",
            "parameters": {"type": "object", "properties": {}},
        },
    }]
    response_1 = MagicMock(status_code=200)
    response_1.json.return_value = {
        "choices": [{"message": {"content": None, "tool_calls": [{
            "id": "call-gated",
            "type": "function",
            "function": {"name": "read_tool", "arguments": "{}"},
        }]}}]
    }
    response_2 = MagicMock(status_code=200)
    response_2.json.return_value = {
        "choices": [{"message": {"content": "The tool was not executed.", "tool_calls": []}}]
    }
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=[response_1, response_2])
    executor = AsyncMock(return_value="executed")

    with patch("httpx.AsyncClient", return_value=mock_client), patch(
        "shogun.services.tool_gate.check_tool_access", new_callable=AsyncMock
    ) as mock_gate:
        if isinstance(gate_outcome, Exception):
            mock_gate.side_effect = gate_outcome
        else:
            mock_gate.return_value = GateDecision(
                action=gate_outcome,
                reason="Approval required",
                risk_level=RiskLevel.MEDIUM,
                tool_name="read_tool",
            )
        result = await flow_engine._call_llm_with_tools(
            messages=[{"role": "user", "content": "Read it"}],
            model_name="test-model",
            base_url="http://localhost:8000",
            headers={},
            tools=tools,
            tool_executor=executor,
            governance_context={"posture_level": "campaign"},
        )

    assert result == "The tool was not executed."
    executor.assert_not_awaited()


@pytest.mark.asyncio
async def test_samurai_text_tool_adapter_executes_canonical_call():
    tools = [{
        "type": "function",
        "function": {
            "name": "read_tool",
            "description": "Read test data",
            "parameters": {"type": "object", "properties": {}},
        },
    }]
    response_1 = MagicMock(status_code=200)
    response_1.json.return_value = {
        "choices": [{"message": {"content": (
            '<tool_call>{"tool":"read_tool","arguments":{}}</tool_call>'
        )}}]
    }
    response_2 = MagicMock(status_code=200)
    response_2.json.return_value = {
        "choices": [{"message": {"content": "Finished from the real result."}}]
    }
    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.post = AsyncMock(side_effect=[response_1, response_2])
    executor = AsyncMock(return_value='{"value":"real"}')

    with patch("httpx.AsyncClient", return_value=mock_client), patch(
        "shogun.services.tool_gate.check_tool_access", new_callable=AsyncMock
    ) as mock_gate:
        mock_gate.return_value = GateDecision(
            action=GateAction.ALLOW,
            reason="Allowed",
            risk_level=RiskLevel.LOW,
            tool_name="read_tool",
        )
        result = await flow_engine._call_llm_with_tools(
            messages=[{"role": "user", "content": "Read it"}],
            model_name="text-model",
            base_url="http://localhost:8000",
            headers={},
            tools=tools,
            tool_executor=executor,
            governance_context={"posture_level": "campaign"},
            tool_profile={"mode": "text", "adapter_id": "shogun_text_v1"},
        )

    assert result == "Finished from the real result."
    executor.assert_awaited_once()
    first_payload = mock_client.post.await_args_list[0].kwargs["json"]
    assert "tools" not in first_payload
    assert "Available Tools" in first_payload["messages"][0]["content"]


@pytest.mark.asyncio
async def test_samurai_tool_scope_contains_only_read_only_artifact_tools():
    tools, _executor = await flow_engine._resolve_samurai_tools({
        "permissions": {
            "filesystem_mode": "scoped",
            "office_enabled": True,
            "office_excel_enabled": True,
            "office_word_enabled": True,
            "office_ppt_enabled": True,
        }
    })
    names = {tool["function"]["name"] for tool in tools}

    assert {"workspace_read", "office_excel_read_range", "file_read"} <= names
    assert not any(
        marker in name
        for name in names
        for marker in ("write", "save", "create", "delete", "send", "export", "transform")
    )
