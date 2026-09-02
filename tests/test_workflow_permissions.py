import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select

import shogun.db.models  # noqa: F401
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.agent_flow import AgentFlow
from shogun.db.models.security_policy import SecurityPolicy
from shogun.services import posture_guard
from shogun.services.native_skills import (
    NATIVE_TOOLS,
    WORKFLOW_TOOL_PERMISSIONS,
    _shogun_workflow_permission,
    execute_native_tool,
)
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
            "set_agent_flow_status",
        }
    ]


def test_workflow_creation_tools_exist_and_activation_is_explicit():
    tools = {tool["function"]["name"]: tool for tool in _workflow_tools()}

    assert set(tools) == {
        "create_agent_flow",
        "edit_agent_flow",
        "delete_agent_flow",
        "set_agent_flow_status",
    }
    for name, tool in tools.items():
        parameters = tool["function"]["parameters"]
        if name.startswith(("create_", "edit_")):
            assert parameters["properties"]["activate"]["type"] == "boolean"
            assert "activate" not in parameters["required"]
        else:
            assert tool["risk"] == ("medium" if name == "set_agent_flow_status" else "high")


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
        "set_agent_flow_status",
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
        "set_agent_flow_status",
    }
    assert denied == []


def test_delete_tools_use_the_explicit_delete_toggles():
    from shogun.services.tool_gate import TOOL_RISK_REGISTRY

    assert WORKFLOW_TOOL_PERMISSIONS["delete_agent_flow"] == ("agentflow", "allow_delete")
    assert "delete_flow_stack" not in WORKFLOW_TOOL_PERMISSIONS
    assert TOOL_RISK_REGISTRY["delete_agent_flow"] == {"risk": "high", "category": "workflow"}
    assert "delete_flow_stack" not in TOOL_RISK_REGISTRY


def test_toolgate_allow_verdict_maps_to_native_workflow_permission():
    from shogun.api.agents import _toolgate_workflow_permissions
    from shogun.services.tool_gate import GateAction

    assert _toolgate_workflow_permissions(
        "create_agent_flow",
        GateAction.ALLOW,
        WORKFLOW_TOOL_PERMISSIONS,
    ) == {("agentflow", "allow_create")}
    assert not _toolgate_workflow_permissions(
        "create_agent_flow",
        GateAction.BLOCK,
        WORKFLOW_TOOL_PERMISSIONS,
    )


@pytest.mark.asyncio
async def test_campaign_toolgate_allow_authorizes_native_agentflow_capability():
    from shogun.api.agents import _toolgate_workflow_permissions
    from shogun.services.tool_gate import GateAction, check_tool_access

    decision = await check_tool_access(
        "campaign",
        "create_agent_flow",
        {},
        local_scope="test:campaign",
    )

    assert decision.action == GateAction.ALLOW
    assert _toolgate_workflow_permissions(
        "create_agent_flow",
        decision.action,
        WORKFLOW_TOOL_PERMISSIONS,
    ) == {("agentflow", "allow_create")}


@pytest.mark.asyncio
async def test_legacy_gensui_block_is_ignored_for_agentflow_create():
    from shogun.api.agents import _toolgate_workflow_permissions
    from shogun.services.tool_gate import (
        GateAction,
        apply_gensui_overrides,
        check_tool_access,
    )

    apply_gensui_overrides({"create_agent_flow": "block"})
    try:
        decision = await check_tool_access(
            "campaign",
            "create_agent_flow",
            {},
            local_scope="test:gensui-block",
        )

        assert decision.action == GateAction.ALLOW
        assert _toolgate_workflow_permissions(
            "create_agent_flow",
            decision.action,
            WORKFLOW_TOOL_PERMISSIONS,
        ) == {("agentflow", "allow_create")}
    finally:
        apply_gensui_overrides({})


@pytest.mark.asyncio
async def test_native_permission_reads_primary_shogun_and_falls_back_to_policy():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        policy = SecurityPolicy(
            name="Campaign AgentFlow",
            tier="campaign",
            permissions={"agentflow": {"allow_create": True}},
        )
        session.add(policy)
        await session.flush()
        legacy = Agent(
            agent_type="shogun",
            name="Legacy Shogun",
            slug="legacy-shogun-permissions",
            status="active",
            is_primary=False,
            bushido_settings={"custom_permissions": {"agentflow": {"allow_create": False}}},
        )
        primary = Agent(
            agent_type="shogun",
            name="Primary Shogun",
            slug="primary-shogun-permissions",
            status="active",
            is_primary=True,
            security_policy_id=policy.id,
            bushido_settings={"custom_permissions": {}},
        )
        session.add_all([legacy, primary])
        await session.flush()

        assert await _shogun_workflow_permission(session, "agentflow", "allow_create")

    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool_name", "flow_type", "argument_name", "permission_category"),
    [
        ("delete_agent_flow", "standard", "flow_id", "agentflow"),
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


@pytest.mark.asyncio
async def test_explicit_operator_authorization_bypasses_disabled_create_permission(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(posture_guard, "get_posture_permissions", lambda: _allowed_posture())

    async with sessions() as session:
        shogun = Agent(
            agent_type="shogun",
            name="Shogun",
            slug="shogun-one-turn-create",
            status="active",
            is_primary=True,
            bushido_settings={"custom_permissions": {"agentflow": {"allow_create": False}}},
        )
        session.add(shogun)
        await session.commit()

        denied = json.loads(await execute_native_tool(
            "create_agent_flow",
            {"name": "Denied without authorization", "nodes": [], "edges": []},
            session,
        ))
        assert denied["status"] == "permission_required"
        assert denied["permission"] == "agentflow.allow_create"

        approved = json.loads(await execute_native_tool(
            "create_agent_flow",
            {"name": "Operator-authorized draft", "nodes": [], "edges": []},
            session,
            operator_confirmed_permissions={("agentflow", "allow_create")},
        ))
        assert approved["status"] == "success", approved
        assert approved["flow_status"] == "draft"

    await engine.dispose()


@pytest.mark.asyncio
async def test_native_create_preserves_scheduled_input_metadata(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", _allowed_posture)

    async with sessions() as session:
        result = json.loads(await execute_native_tool(
            "create_agent_flow",
            {
                "name": "Scheduled News",
                "nodes": [{
                    "id": "schedule",
                    "node_type": "input",
                    "label": "Weekdays at 08:00",
                    "config": {
                        "input_type": "scheduled",
                        "schedule_frequency": "weekly",
                        "schedule_time": "08:00",
                        "schedule_days": ["mon", "tue", "wed", "thu", "fri"],
                    },
                }],
                "edges": [],
            },
            session,
            operator_confirmed_permissions={("agentflow", "allow_create")},
        ))
        flow = (await session.execute(select(AgentFlow).where(AgentFlow.id == result["flow_id"]))).scalar_one()
        assert result["status"] == "success"
        assert flow.trigger_type == "scheduled"
        assert flow.schedule_config["schedule_time"] == "08:00"
        assert flow.schedule_config["schedule_days"] == ["mon", "tue", "wed", "thu", "fri"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_campaign_can_activate_and_pause_agentflow_without_profile_toggle(monkeypatch):
    from shogun.api import agent_flow as agent_flow_api

    async def campaign_posture():
        return {**(await _allowed_posture()), "active_tier": "campaign"}

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", campaign_posture)
    sync_schedule = AsyncMock()
    monkeypatch.setattr(agent_flow_api, "_sync_live_flow_schedule", sync_schedule)

    async with sessions() as session:
        shogun = Agent(
            agent_type="shogun",
            name="Shogun",
            slug="shogun-campaign-lifecycle",
            status="active",
            is_primary=True,
            bushido_settings={"custom_permissions": {"agentflow": {"allow_activate": False}}},
        )
        flow = AgentFlow(name="Campaign flow", flow_type="standard", status="draft")
        session.add_all([shogun, flow])
        await session.commit()

        activated = json.loads(await execute_native_tool(
            "set_agent_flow_status", {"flow_id": str(flow.id), "status": "active"}, session
        ))
        paused = json.loads(await execute_native_tool(
            "set_agent_flow_status", {"flow_id": str(flow.id), "status": "paused"}, session
        ))
        assert activated["status"] == "success"
        assert activated["posture"] == "campaign"
        assert paused["flow_status"] == "paused"
        assert sync_schedule.await_count == 2

    await engine.dispose()


@pytest.mark.asyncio
async def test_explicit_operator_authorization_bypasses_disabled_full_edit_permission(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(posture_guard, "get_posture_permissions", lambda: _allowed_posture())

    async with sessions() as session:
        shogun = Agent(
            agent_type="shogun",
            name="Shogun",
            slug="shogun-one-turn-edit",
            status="active",
            is_primary=True,
            bushido_settings={"custom_permissions": {"agentflow": {"allow_edit": False}}},
        )
        flow = AgentFlow(name="Before edit", flow_type="standard")
        session.add_all([shogun, flow])
        await session.commit()

        approved = json.loads(await execute_native_tool(
            "edit_agent_flow",
            {"flow_id": str(flow.id), "name": "After edit"},
            session,
            operator_confirmed_permissions={("agentflow", "allow_edit")},
        ))
        assert approved["status"] == "success", approved
        assert approved["flow_status"] == "draft"
        await session.refresh(flow)
        assert flow.name == "After edit"

    await engine.dispose()


async def _allowed_posture():
    return {"active_tier": "tactical", "agentflow_create": True, "flowstack_create": True}
