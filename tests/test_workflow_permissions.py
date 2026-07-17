import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.agent_flow import AgentFlow
from shogun.services import posture_guard
from shogun.services.native_skills import NATIVE_TOOLS, WORKFLOW_TOOL_PERMISSIONS, execute_native_tool
from shogun.services.posture_guard import filter_tools_by_posture


def _workflow_tools():
    return [
        tool
        for tool in NATIVE_TOOLS
        if tool["function"]["name"]
        in {
            "create_agent_flow",
            "edit_agent_flow",
            "delete_agent_flow",
            "create_flow_stack",
            "edit_flow_stack",
            "delete_flow_stack",
        }
    ]


def test_workflow_creation_tools_exist_and_activation_is_explicit():
    tools = {tool["function"]["name"]: tool for tool in _workflow_tools()}

    assert set(tools) == {
        "create_agent_flow",
        "edit_agent_flow",
        "delete_agent_flow",
        "create_flow_stack",
        "edit_flow_stack",
        "delete_flow_stack",
    }
    for name, tool in tools.items():
        parameters = tool["function"]["parameters"]
        if name.startswith(("create_", "edit_")):
            assert parameters["properties"]["activate"]["type"] == "boolean"
            assert "activate" not in parameters["required"]
        else:
            assert tool["risk"] == "high"


def test_workflow_tools_are_blocked_below_tactical_posture():
    allowed, denied = filter_tools_by_posture(
        _workflow_tools(),
        {"agentflow_create": False, "flowstack_create": False},
    )

    assert allowed == []
    assert set(denied) == {
        "create_agent_flow",
        "edit_agent_flow",
        "delete_agent_flow",
        "create_flow_stack",
        "edit_flow_stack",
        "delete_flow_stack",
    }


def test_workflow_tools_are_posture_eligible_at_tactical_and_above():
    allowed, denied = filter_tools_by_posture(
        _workflow_tools(),
        {"agentflow_create": True, "flowstack_create": True},
    )

    assert {tool["function"]["name"] for tool in allowed} == {
        "create_agent_flow",
        "edit_agent_flow",
        "delete_agent_flow",
        "create_flow_stack",
        "edit_flow_stack",
        "delete_flow_stack",
    }
    assert denied == []


def test_delete_tools_use_the_explicit_delete_toggles():
    assert WORKFLOW_TOOL_PERMISSIONS["delete_agent_flow"] == ("agentflow", "allow_delete")
    assert WORKFLOW_TOOL_PERMISSIONS["delete_flow_stack"] == ("flow_stack", "allow_delete")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "flow_type", "argument_name", "permission_category"),
    [
        ("delete_agent_flow", "standard", "flow_id", "agentflow"),
        ("delete_flow_stack", "stack", "flow_stack_id", "flow_stack"),
    ],
)
async def test_enabled_delete_tool_soft_deletes_the_requested_workflow(
    monkeypatch,
    tool_name,
    flow_type,
    argument_name,
    permission_category,
):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(
        posture_guard,
        "get_posture_permissions",
        lambda: _allowed_posture(),
    )
    async with sessions() as session:
        shogun = Agent(
            agent_type="shogun",
            name="Shogun",
            slug=f"shogun-{flow_type}",
            status="active",
            is_primary=True,
            bushido_settings={"custom_permissions": {permission_category: {"allow_delete": True}}},
        )
        flow = AgentFlow(name=f"Delete {flow_type}", flow_type=flow_type)
        session.add_all([shogun, flow])
        await session.commit()
        result = json.loads(await execute_native_tool(tool_name, {argument_name: str(flow.id)}, session))
        await session.refresh(flow)

        assert result["status"] == "success"
        assert result["deleted"] is True
        assert flow.is_deleted is True
    await engine.dispose()


async def _allowed_posture():
    return {"agentflow_create": True, "flowstack_create": True}
