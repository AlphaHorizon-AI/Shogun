"""Native tools for inspecting and safely patching AgentFlow graphs."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.agent_flow import AgentFlow, AgentFlowEdge, AgentFlowNode
from shogun.services import posture_guard
from shogun.services.native_skills import NATIVE_TOOLS, WORKFLOW_TOOL_PERMISSIONS, execute_native_tool
from shogun.services.posture_guard import filter_tools_by_posture


def test_workflow_inspection_and_patch_tools_are_exposed() -> None:
    tools = {tool["function"]["name"]: tool for tool in NATIVE_TOOLS}

    assert tools["get_agent_flow"]["risk"] == "low"
    assert tools["get_flow_stack"]["risk"] == "low"
    assert tools["patch_agent_flow"]["risk"] == "medium"
    assert "get_agent_flow" not in WORKFLOW_TOOL_PERMISSIONS
    assert "get_flow_stack" not in WORKFLOW_TOOL_PERMISSIONS
    assert WORKFLOW_TOOL_PERMISSIONS["patch_agent_flow"] == ("agentflow", "allow_edit")


def test_read_tools_remain_available_when_write_posture_is_disabled() -> None:
    selected = [
        tool
        for tool in NATIVE_TOOLS
        if tool["function"]["name"] in {"get_agent_flow", "get_flow_stack", "patch_agent_flow"}
    ]

    allowed, denied = filter_tools_by_posture(
        selected,
        {"agentflow_create": False, "flowstack_create": False},
    )

    assert {tool["function"]["name"] for tool in allowed} == {"get_agent_flow", "get_flow_stack"}
    assert denied == ["patch_agent_flow"]


@pytest.mark.asyncio
async def test_read_tools_return_complete_flow_and_stack_graphs() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        flow = AgentFlow(name="Daily AI Brief", flow_type="standard", description="AI-only news")
        stack = AgentFlow(name="Daily Brief Stack", flow_type="stack")
        session.add_all([flow, stack])
        await session.flush()

        input_node = AgentFlowNode(
            flow_id=flow.id,
            node_type="input",
            label="Schedule",
            position_x=0,
            config={"input_type": "scheduled"},
        )
        source_node = AgentFlowNode(
            flow_id=flow.id,
            node_type="mado_browser",
            label="AI Sources",
            position_x=300,
            config={"query": "AI news", "domains": ["openai.com"]},
        )
        stack_input = AgentFlowNode(flow_id=stack.id, node_type="input", label="Stack Input", position_x=0)
        phase = AgentFlowNode(
            flow_id=stack.id,
            node_type="subflow",
            label="Research phase",
            position_x=300,
            config={
                "child_flow_id": str(flow.id),
                "child_flow_version_mode": "locked",
                "child_flow_version": 1,
                "input_mapping": {"topic": "topic"},
                "output_mapping": {"brief": "result"},
            },
        )
        session.add_all([input_node, source_node, stack_input, phase])
        await session.flush()
        session.add_all([
            AgentFlowEdge(flow_id=flow.id, source_node_id=input_node.id, target_node_id=source_node.id),
            AgentFlowEdge(flow_id=stack.id, source_node_id=stack_input.id, target_node_id=phase.id),
        ])
        await session.commit()

        flow_result = json.loads(await execute_native_tool("get_agent_flow", {"flow_id": str(flow.id)}, session))
        stack_result = json.loads(
            await execute_native_tool("get_flow_stack", {"flow_stack_id": str(stack.id)}, session)
        )

        assert flow_result["status"] == "success"
        assert flow_result["flow"]["name"] == "Daily AI Brief"
        assert len(flow_result["flow"]["nodes"]) == 2
        assert len(flow_result["flow"]["edges"]) == 1
        assert flow_result["flow"]["nodes"][1]["config"]["domains"] == ["openai.com"]
        assert stack_result["status"] == "success"
        assert stack_result["flow"]["flow_type"] == "stack"
        assert stack_result["flow"]["phases"] == [{
            "phase": 1,
            "node_id": str(phase.id),
            "label": "Research phase",
            "child_flow_id": str(flow.id),
            "version_mode": "locked",
            "child_flow_version": 1,
            "execution_mode": None,
            "timeout_seconds": None,
            "on_failure": None,
            "input_mapping": {"topic": "topic"},
            "output_mapping": {"brief": "result"},
        }]

    await engine.dispose()


@pytest.mark.asyncio
async def test_patch_agent_flow_preserves_untouched_graph_elements(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(posture_guard, "get_posture_permissions", lambda: _allowed_posture())

    async with sessions() as session:
        shogun = Agent(
            agent_type="shogun",
            name="Shogun",
            slug="shogun-flow-reader",
            status="active",
            is_primary=True,
            bushido_settings={"custom_permissions": {"agentflow": {"allow_edit": True}}},
        )
        flow = AgentFlow(name="Patch safely", flow_type="standard")
        session.add_all([shogun, flow])
        await session.flush()
        input_node = AgentFlowNode(flow_id=flow.id, node_type="input", label="Input", position_x=0)
        research_node = AgentFlowNode(
            flow_id=flow.id,
            node_type="samurai",
            label="Research",
            position_x=300,
            config={"topic": "technology", "keep": True},
        )
        session.add_all([input_node, research_node])
        await session.flush()
        original_edge = AgentFlowEdge(
            flow_id=flow.id,
            source_node_id=input_node.id,
            target_node_id=research_node.id,
        )
        session.add(original_edge)
        await session.commit()

        new_node_id = uuid.uuid4()
        result = json.loads(await execute_native_tool(
            "patch_agent_flow",
            {
                "flow_id": str(flow.id),
                "node_operations": [
                    {
                        "op": "update",
                        "node_id": str(research_node.id),
                        "config_patch": {"topic": "AI news", "sources_only": True},
                    },
                    {
                        "op": "add",
                        "node_id": str(new_node_id),
                        "node_type": "mado_browser",
                        "label": "Additional AI sources",
                        "position_x": 600,
                        "config": {"query": "latest AI research"},
                    },
                ],
                "edge_operations": [{
                    "op": "add",
                    "source_node_id": str(research_node.id),
                    "target_node_id": str(new_node_id),
                }],
            },
            session,
        ))

        nodes = {node["node_id"]: node for node in result["flow"]["nodes"]}
        edge_ids = {edge["edge_id"] for edge in result["flow"]["edges"]}
        assert result["status"] == "success"
        assert nodes[str(input_node.id)]["label"] == "Input"
        assert nodes[str(research_node.id)]["config"] == {
            "topic": "AI news",
            "keep": True,
            "sources_only": True,
        }
        assert nodes[str(new_node_id)]["node_type"] == "mado_browser"
        assert str(original_edge.id) in edge_ids
        assert len(edge_ids) == 2

    await engine.dispose()


async def _allowed_posture() -> dict[str, bool]:
    return {"agentflow_create": True, "flowstack_create": True}
