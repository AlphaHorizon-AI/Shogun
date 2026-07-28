from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from shogun.api.agent_flow import _validate_agentflow_tool_contract
from shogun.engine import flow_engine
from shogun.schemas.agent_flow import AgentFlowNodeCreate
from shogun.services import native_skills, posture_guard, tool_gate
from shogun.services.event_logger import EventLogger


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _allowed_posture() -> dict:
    return {
        "kill_switch_active": False,
        "active_tier": "tactical",
        "active_policy_id": None,
        "active_policy_name": None,
        "active_policy_is_builtin": True,
        "active_policy_tier": "tactical",
        "comms_read_email": True,
        "comms_read_calendar": True,
    }


@pytest.mark.asyncio
async def test_email_read_executes_governed_native_tool_and_filters_unread(monkeypatch):
    calls: list[tuple[str, dict]] = []

    async def posture():
        return _allowed_posture()

    async def allow(*_args, **_kwargs):
        return tool_gate.GateDecision(
            action=tool_gate.GateAction.ALLOW,
            reason="test allow",
            risk_level=tool_gate.RiskLevel.LOW,
            tool_name="fetch_inbox",
        )

    async def execute(name, args, _session):
        calls.append((name, args))
        return json.dumps(
            {
                "status": "success",
                "messages": [
                    {"uid": "1", "subject": "Unread", "is_read": False},
                    {"uid": "2", "subject": "Read", "is_read": True},
                ],
            }
        )

    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", posture)
    monkeypatch.setattr(tool_gate, "check_tool_access", allow)
    monkeypatch.setattr(native_skills, "execute_native_tool", execute)

    result = await flow_engine._exec_email_read(
        {"folder": "INBOX", "page": 1, "per_page": 20, "unread_only": True}
    )

    assert calls == [("fetch_inbox", {"folder": "INBOX", "page": 1, "per_page": 20})]
    assert [message["uid"] for message in result["messages"]] == ["1"]
    assert result["returned"] == 1


@pytest.mark.asyncio
async def test_calendar_read_passes_explicit_bounded_range(monkeypatch):
    calls: list[tuple[str, dict]] = []

    async def posture():
        return _allowed_posture()

    async def allow(*_args, **_kwargs):
        return tool_gate.GateDecision(
            action=tool_gate.GateAction.ALLOW,
            reason="test allow",
            risk_level=tool_gate.RiskLevel.LOW,
            tool_name="list_calendar_events",
        )

    async def execute(name, args, _session):
        calls.append((name, args))
        return json.dumps({"status": "success", "count": 0, "events": []})

    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", posture)
    monkeypatch.setattr(tool_gate, "check_tool_access", allow)
    monkeypatch.setattr(native_skills, "execute_native_tool", execute)

    result = await flow_engine._exec_calendar_read(
        {"start_date": "2026-07-28T00:00:00+02:00", "end_date": "2026-07-29T00:00:00+02:00"}
    )

    assert result["events"] == []
    assert calls == [
        (
            "list_calendar_events",
            {
                "start_date": "2026-07-28T00:00:00+02:00",
                "end_date": "2026-07-29T00:00:00+02:00",
            },
        )
    ]


@pytest.mark.asyncio
async def test_unattended_native_read_does_not_bypass_confirmation(monkeypatch):
    async def posture():
        return _allowed_posture()

    async def confirm(*_args, **_kwargs):
        return tool_gate.GateDecision(
            action=tool_gate.GateAction.CONFIRM,
            reason="operator confirmation required",
            risk_level=tool_gate.RiskLevel.LOW,
            tool_name="fetch_inbox",
        )

    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", posture)
    monkeypatch.setattr(tool_gate, "check_tool_access", confirm)

    with pytest.raises(PermissionError, match="cannot run unattended"):
        await flow_engine._exec_email_read({})


def test_samurai_tool_request_is_rejected_when_graph_is_saved():
    with pytest.raises(ValueError, match="Email Read"):
        _validate_agentflow_tool_contract(
            [
                {
                    "node_type": "samurai",
                    "label": "Compile Brief",
                    "config": {"task_description": "Call fetch_inbox and summarize the messages."},
                }
            ]
        )


@pytest.mark.asyncio
async def test_samurai_runtime_rejects_native_tool_request_with_actionable_replacement():
    with pytest.raises(ValueError, match="Calendar Read"):
        await flow_engine._exec_samurai(
            {"task_description": "Use list_calendar_events for today."},
            "",
        )


def test_native_read_node_configs_are_normalized_and_bounded():
    email = AgentFlowNodeCreate(node_type="email_read", config={})
    calendar = AgentFlowNodeCreate(node_type="calendar_read", config={"days_ahead": 1})

    assert email.config == {"folder": "INBOX", "page": 1, "per_page": 10, "unread_only": True}
    assert calendar.config["days_ahead"] == 1

    with pytest.raises(ValidationError):
        AgentFlowNodeCreate(node_type="email_read", config={"per_page": 1000})
    with pytest.raises(ValidationError):
        AgentFlowNodeCreate(node_type="calendar_read", config={"days_ahead": 0})
    with pytest.raises(ValidationError):
        AgentFlowNodeCreate(node_type="calendar_read", config={"start_date": "2026-07-28T00:00:00"})


@pytest.mark.asyncio
async def test_node_failure_event_is_deep_linkable_and_contains_exact_error(monkeypatch):
    captured: dict = {}

    async def emit(event_type, action, **kwargs):
        captured.update({"event_type": event_type, "action": action, **kwargs})
        return "evt_failure_123"

    monkeypatch.setattr(EventLogger, "emit_incident_event", emit)
    run_id = uuid.uuid4()
    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="samurai",
        label="Compile Morning Brief",
    )

    event_id = await flow_engine._record_node_failure_event(
        run_id,
        node,
        RuntimeError("Calendar connector returned 401: token expired"),
    )

    assert event_id == "evt_failure_123"
    assert captured["event_type"] == "agent_flow.node.failed"
    assert captured["result"] == "error"
    assert captured["trace_id"] == str(run_id)
    assert captured["detail"]["node_id"] == str(node.id)
    assert captured["detail"]["error"] == "Calendar connector returned 401: token expired"
