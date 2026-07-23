"""Native tools for inspecting and safely patching AgentFlow graphs."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.api.agents import (
    _classify_chat_mode,
    _filter_tools_by_intent,
    _operator_authorizes_agentflow_patch,
)
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.agent_flow import AgentFlow, AgentFlowEdge, AgentFlowNode
from shogun.services import posture_guard
from shogun.services.native_skills import (
    NATIVE_TOOLS,
    WORKFLOW_ONE_TIME_CONFIRM_TOOLS,
    WORKFLOW_TOOL_PERMISSIONS,
    execute_native_tool,
)
from shogun.services.posture_guard import filter_tools_by_posture
from shogun.services.workflow_operator import (
    WORKFLOW_MUTATION_TOOLS,
    WORKFLOW_OPERATOR_GUIDE,
    is_workflow_request,
    operator_authorized_workflow_tools,
    requires_workflow_tools,
)


def test_workflow_inspection_and_patch_tools_are_exposed() -> None:
    tools = {tool["function"]["name"]: tool for tool in NATIVE_TOOLS}

    assert tools["get_agent_flow"]["risk"] == "low"
    assert tools["get_flow_stack"]["risk"] == "low"
    assert tools["patch_agent_flow"]["risk"] == "medium"
    assert tools["set_agent_flow_status"]["risk"] == "medium"
    assert "get_agent_flow" not in WORKFLOW_TOOL_PERMISSIONS
    assert "get_flow_stack" not in WORKFLOW_TOOL_PERMISSIONS
    assert WORKFLOW_TOOL_PERMISSIONS["patch_agent_flow"] == ("agentflow", "allow_edit")
    assert WORKFLOW_TOOL_PERMISSIONS["set_agent_flow_status"] == ("agentflow", "allow_activate")
    assert WORKFLOW_ONE_TIME_CONFIRM_TOOLS == set(WORKFLOW_TOOL_PERMISSIONS)


def test_direct_agentflow_edit_instruction_is_one_turn_authorization() -> None:
    assert _operator_authorizes_agentflow_patch(
        "Inspect Daily AI Brief first, then edit the AgentFlow and add two AI sources."
    )
    assert _operator_authorizes_agentflow_patch("Update my workflow nodes and replace the BBC source.")
    assert not _operator_authorizes_agentflow_patch("Show me the current AgentFlow structure.")
    assert not _operator_authorizes_agentflow_patch("Do not edit the AgentFlow; only inspect it.")


def test_workflow_requests_always_select_mission_and_retain_workflow_tools() -> None:
    for request in (
        "Create a new AgentFlow for the daily brief.",
        "Delete my AI News Brief flow.",
        "Build a Flow Stack from the research and writing flows.",
        "Show me the stack orchestrator pipeline.",
    ):
        assert is_workflow_request(request)
        assert requires_workflow_tools(request)
        classification = _classify_chat_mode(request, [])
        assert classification["mode"] == "mission"

    assert is_workflow_request("What is an AgentFlow?")
    assert not requires_workflow_tools("What is an AgentFlow?")

    selected = _filter_tools_by_intent(NATIVE_TOOLS, ["news", "workflow"], True)
    selected_names = {tool["function"]["name"] for tool in selected}
    assert "list_agent_flows" in selected_names
    assert "get_agent_flow" in selected_names
    assert "create_agent_flow" in selected_names


def test_workflow_operator_guide_is_fixed_and_requires_verified_execution() -> None:
    assert "Call `list_agent_flows` before" in WORKFLOW_OPERATOR_GUIDE
    assert "`channel_send` node for Telegram or Teams" in WORKFLOW_OPERATOR_GUIDE
    assert "Do not tell a Telegram or Teams operator" in WORKFLOW_OPERATOR_GUIDE
    assert "Never claim" in WORKFLOW_OPERATOR_GUIDE
    assert "A UUID cannot bypass that mismatch" in WORKFLOW_OPERATOR_GUIDE
    assert "### `coding`" in WORKFLOW_OPERATOR_GUIDE
    assert "project-scoped programming memory" in WORKFLOW_OPERATOR_GUIDE


@pytest.mark.asyncio
async def test_empty_flow_list_reports_database_mismatch_diagnostic() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        result = json.loads(await execute_native_tool("list_agent_flows", {}, session))

    assert result["status"] == "success"
    assert result["total"] == 0
    assert result["diagnostic"]["result_kind"] == "successful_empty_query"
    assert result["diagnostic"]["toolgate_blocked"] is False
    assert result["diagnostic"]["visible_unfiltered_total"] == 0
    assert len(result["diagnostic"]["database_fingerprint"]) == 12
    assert "UUID will not bypass" in result["diagnostic"]["explanation"]

    await engine.dispose()


def test_explicit_workflow_writes_authorize_medium_risk_tools_only() -> None:
    assert operator_authorized_workflow_tools("Create an AgentFlow for daily news.") == {
        "create_agent_flow"
    }
    assert operator_authorized_workflow_tools("Edit the Daily Brief flow and replace its source.") == {
        "patch_agent_flow",
        "edit_agent_flow",
    }
    assert operator_authorized_workflow_tools("Build a Flow Stack from these flows.") == {
        "create_flow_stack"
    }
    assert operator_authorized_workflow_tools("Delete the Daily Brief AgentFlow.") == set()
    assert operator_authorized_workflow_tools("Do not edit the AgentFlow; inspect it.") == set()
    assert operator_authorized_workflow_tools("Activate the Daily Brief AgentFlow.") == {
        "set_agent_flow_status"
    }
    assert WORKFLOW_MUTATION_TOOLS == set(WORKFLOW_TOOL_PERMISSIONS)


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


@pytest.mark.asyncio
async def test_patch_agent_flow_accepts_one_time_operator_confirmation(monkeypatch) -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(posture_guard, "get_posture_permissions", lambda: _allowed_posture())

    async with sessions() as session:
        shogun = Agent(
            agent_type="shogun",
            name="Shogun",
            slug="shogun-confirmed-flow-editor",
            status="active",
            is_primary=True,
            bushido_settings={"custom_permissions": {"agentflow": {"allow_edit": False}}},
        )
        flow = AgentFlow(name="One-time approval", flow_type="standard")
        session.add_all([shogun, flow])
        await session.commit()

        denied = json.loads(await execute_native_tool(
            "patch_agent_flow",
            {"flow_id": str(flow.id), "node_operations": [], "edge_operations": []},
            session,
        ))
        assert denied["status"] == "permission_required"
        assert denied["permission"] == "agentflow.allow_edit"

        approved = json.loads(await execute_native_tool(
            "patch_agent_flow",
            {
                "flow_id": str(flow.id),
                "node_operations": [{"op": "add", "node_type": "input", "label": "Input"}],
                "edge_operations": [],
            },
            session,
            operator_confirmed_permissions={("agentflow", "allow_edit")},
        ))
        assert approved["status"] == "success", approved

    await engine.dispose()


async def _allowed_posture() -> dict[str, bool]:
    return {"agentflow_create": True, "flowstack_create": True}
