"""Tests for deterministic Agent Flow output memory infusion."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from shogun.schemas.agent_flow import AgentFlowNodeCreate, MemoryInfusionConfig
from shogun.services import flow_memory_infusion as infusion


def _ids() -> dict[str, uuid.UUID]:
    return {name: uuid.uuid4() for name in ("agent", "flow", "run", "node", "memory")}


def test_output_node_normalizes_memory_infusion_defaults() -> None:
    node = AgentFlowNodeCreate(
        node_type="output",
        config={"memory_infusion": {"enabled": True}},
    )

    config = node.config["memory_infusion"]
    assert config["enabled"] is True
    assert config["store_on"] == "success"
    assert config["redact_sensitive"] is True
    assert config["deduplication"] == {"mode": "exact", "semantic_threshold": 0.92}


def test_memory_infusion_rejects_unknown_title_placeholder() -> None:
    with pytest.raises(ValidationError, match="Unsupported title_template placeholders"):
        MemoryInfusionConfig(enabled=True, title_template="{flow_name} - {unknown}")


def test_redact_sensitive_content_removes_common_credentials() -> None:
    content = "api_key=supersecret Bearer abcdefghijklmnopqrst ghp_abcdefghijklmnop"

    redacted = infusion.redact_sensitive_content(content)

    assert "supersecret" not in redacted
    assert "abcdefghijklmnopqrst" not in redacted
    assert "ghp_abcdefghijklmnop" not in redacted
    assert redacted.count("[REDACTED]") == 3


@pytest.mark.asyncio
async def test_infuse_stores_selected_fields_with_provenance_and_redaction(monkeypatch) -> None:
    ids = _ids()
    session = SimpleNamespace(scalar=AsyncMock(side_effect=[SimpleNamespace(id=ids["agent"]), None]))
    created = SimpleNamespace(id=ids["memory"])
    create_memory = AsyncMock(return_value=created)
    monkeypatch.setattr(infusion.MemoryService, "create_memory", create_memory)
    monkeypatch.setattr(infusion.EventLogger, "emit", AsyncMock(return_value="evt_test"))

    result = await infusion.infuse_flow_output_memory(
        session=session,
        raw_config={
            "enabled": True,
            "content_fields": ["result", "summary"],
            "title_template": "{flow_name} - {node_label}",
        },
        flow_id=ids["flow"],
        flow_name="Research Flow",
        run_id=ids["run"],
        node_id=ids["node"],
        node_label="Final answer",
        output="api_key=supersecret\nUseful result",
        predecessor_outputs={"research": {"summary": "Verified summary; password=hunter2"}},
    )

    assert result.action == "stored"
    kwargs = create_memory.await_args.kwargs
    assert kwargs["agent_id"] == ids["agent"]
    assert kwargs["title"] == "Research Flow - Final answer"
    assert "supersecret" not in kwargs["content"]
    assert "[REDACTED]" in kwargs["content"]
    assert "Verified summary" in kwargs["content"]
    assert "hunter2" not in kwargs["summary"]
    assert kwargs["source_type"] == "flow_output"
    assert kwargs["source_ref_id"] == ids["run"]
    assert kwargs["source_external_id"] == f'{ids["flow"]}:{ids["node"]}:{ids["run"]}'
    assert f'flow:{ids["flow"]}' in kwargs["tags"]
    assert kwargs["decay_class"] == "sticky"
    assert kwargs["is_pinned"] is False


@pytest.mark.asyncio
async def test_infuse_reinforces_exact_duplicate_instead_of_storing(monkeypatch) -> None:
    ids = _ids()
    existing = SimpleNamespace(id=ids["memory"])
    session = SimpleNamespace(
        scalar=AsyncMock(side_effect=[SimpleNamespace(id=ids["agent"]), existing])
    )
    create_memory = AsyncMock()
    reinforce = AsyncMock()
    monkeypatch.setattr(infusion.MemoryService, "create_memory", create_memory)
    monkeypatch.setattr(infusion.MemoryService, "reinforce", reinforce)
    monkeypatch.setattr(infusion.EventLogger, "emit", AsyncMock(return_value="evt_test"))

    result = await infusion.infuse_flow_output_memory(
        session=session,
        raw_config={"enabled": True, "content_fields": ["result"]},
        flow_id=ids["flow"],
        flow_name="Flow",
        run_id=ids["run"],
        node_id=ids["node"],
        node_label="Output",
        output="Repeated durable result",
        predecessor_outputs={},
    )

    assert result.action == "deduplicated"
    assert result.reason == "exact match"
    reinforce.assert_awaited_once_with(ids["memory"], "reused_across_sessions")
    create_memory.assert_not_awaited()


@pytest.mark.asyncio
async def test_infuse_honors_missing_field_and_status_policies(monkeypatch) -> None:
    audit = AsyncMock(return_value="evt_test")
    monkeypatch.setattr(infusion.EventLogger, "emit", audit)
    ids = _ids()
    common = {
        "session": SimpleNamespace(scalar=AsyncMock()),
        "flow_id": ids["flow"],
        "flow_name": "Flow",
        "run_id": ids["run"],
        "node_id": ids["node"],
        "node_label": "Output",
        "output": "Result",
    }

    status_result = await infusion.infuse_flow_output_memory(
        **common,
        raw_config={"enabled": True, "store_on": "partial"},
        predecessor_outputs={},
    )
    field_result = await infusion.infuse_flow_output_memory(
        **common,
        raw_config={
            "enabled": True,
            "content_fields": ["missing"],
            "on_missing_field": "skip",
        },
        predecessor_outputs={},
    )

    assert status_result.action == "status_skipped"
    assert field_result.action == "field_skipped"
    common["session"].scalar.assert_not_awaited()
