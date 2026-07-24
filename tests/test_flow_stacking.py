from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.api.agent_flow import _validate_subflow_graph, create_flow_stack, get_run_tree
from shogun.db.models.agent_flow import AgentFlow, AgentFlowEdge, AgentFlowNode
from shogun.db.models.agent_flow_run import AgentFlowRun, AgentFlowRunEdge
from shogun.engine import flow_engine
from shogun.schemas.agent_flow import FlowStackCreate
from shogun.services.agent_flow_service import AgentFlowService
from shogun.services.event_logger import EventLogger


@pytest.fixture
async def flow_sessions(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        for table in (
            AgentFlow.__table__,
            AgentFlowNode.__table__,
            AgentFlowEdge.__table__,
            AgentFlowRun.__table__,
            AgentFlowRunEdge.__table__,
        ):
            await connection.run_sync(table.create)

    monkeypatch.setattr(flow_engine, "async_session_factory", sessions)
    monkeypatch.setattr(flow_engine, "_child_run_semaphore", None)
    monkeypatch.setattr(EventLogger, "emit_governance_event", AsyncMock(return_value="evt_test"))

    yield sessions
    await engine.dispose()


def test_flow_mapping_preserves_structured_exact_values():
    context = {
        "input": {"topic": "quarterly results", "limits": {"pages": 8}},
        "node": {"research": {"output": {"sources": ["a", "b"]}}},
    }

    mapped = flow_engine.resolve_flow_mapping(
        {
            "topic": "{{input.topic}}",
            "limits": "{{input.limits}}",
            "sources": "{{node.research.output.sources}}",
            "title": "Report: {{input.topic}}",
        },
        context,
    )

    assert mapped == {
        "topic": "quarterly results",
        "limits": {"pages": 8},
        "sources": ["a", "b"],
        "title": "Report: quarterly results",
    }


def test_child_permission_ceiling_blocks_required_tool():
    governance = {
        "allowed_tools": ["workspace"],
        "permissions": {"workspace_enabled": True, "office_enabled": False},
    }

    with pytest.raises(ValueError, match="office"):
        flow_engine._validate_child_permissions(governance, ["workspace", "office"])


@pytest.mark.asyncio
async def test_subflow_validation_ignores_unrelated_broken_flow(flow_sessions):
    target_id = uuid.uuid4()
    unrelated_id = uuid.uuid4()
    missing_id = uuid.uuid4()

    async with flow_sessions() as session:
        session.add_all([
            AgentFlow(id=target_id, name="Editable", schedule_config={}, viewport={}),
            AgentFlow(id=unrelated_id, name="Legacy broken flow", schedule_config={}, viewport={}),
            AgentFlowNode(
                flow_id=unrelated_id,
                node_type="subflow",
                label="Missing child",
                config={
                    "child_flow_id": str(missing_id),
                    "child_flow_version_mode": "latest",
                },
            ),
        ])
        await session.commit()

        warnings = await _validate_subflow_graph(session, target_id, [])

    assert warnings == []


@pytest.mark.asyncio
async def test_subflow_validation_checks_broken_references_reachable_from_target(flow_sessions):
    target_id = uuid.uuid4()
    child_id = uuid.uuid4()
    missing_id = uuid.uuid4()

    async with flow_sessions() as session:
        session.add_all([
            AgentFlow(id=target_id, name="Editable", schedule_config={}, viewport={}),
            AgentFlow(id=child_id, name="Reachable child", schedule_config={}, viewport={}),
            AgentFlowNode(
                flow_id=child_id,
                node_type="subflow",
                label="Missing grandchild",
                config={
                    "child_flow_id": str(missing_id),
                    "child_flow_version_mode": "latest",
                },
            ),
        ])
        await session.commit()

        proposed = [{
            "node_type": "subflow",
            "config": {
                "child_flow_id": str(child_id),
                "child_flow_version_mode": "latest",
            },
        }]
        with pytest.raises(ValueError, match=f"Subflow reference {missing_id} does not exist"):
            await _validate_subflow_graph(session, target_id, proposed)


@pytest.mark.asyncio
async def test_parent_executes_child_and_persists_execution_tree(flow_sessions):
    child_flow_id = uuid.uuid4()
    child_node_id = uuid.uuid4()
    parent_flow_id = uuid.uuid4()
    parent_node_id = uuid.uuid4()
    root_run_id = uuid.uuid4()

    async with flow_sessions() as session:
        child = AgentFlow(
            id=child_flow_id,
            name="Reusable Research",
            description="",
            status="active",
            trigger_type="manual",
            schedule_config={},
            viewport={},
            version=3,
            allow_as_subflow=True,
            required_tools=[],
        )
        parent = AgentFlow(
            id=parent_flow_id,
            name="Board Report Stack",
            description="",
            status="active",
            trigger_type="manual",
            schedule_config={},
            viewport={},
            version=1,
        )
        child_node = AgentFlowNode(
            id=child_node_id,
            flow_id=child_flow_id,
            node_type="input",
            label="Child Input",
            config={"input_type": "api"},
        )
        parent_node = AgentFlowNode(
            id=parent_node_id,
            flow_id=parent_flow_id,
            node_type="subflow",
            label="Run Research",
            config={
                "child_flow_id": str(child_flow_id),
                "child_flow_version_mode": "locked",
                "child_flow_version": 3,
                "input_mapping": {"topic": "{{input.topic}}"},
                "timeout_seconds": 5,
                "on_failure": "fail_parent",
            },
        )
        root_run = AgentFlowRun(
            id=root_run_id,
            flow_id=parent_flow_id,
            flow_version=1,
            root_run_id=root_run_id,
            run_depth=0,
            status="pending",
            trigger_type="manual",
            node_states={},
            result_summary={},
            input_payload={"input": {"topic": "AI governance"}},
            output_payload={},
            artifacts=[],
            governance_context={
                "posture_level": "tactical",
                "permissions": {"workspace_enabled": True},
            },
        )
        session.add_all([child, parent, child_node, parent_node, root_run])
        await session.commit()

    await flow_engine._execute_flow(root_run_id, parent_flow_id)

    async with flow_sessions() as session:
        root = await session.get(AgentFlowRun, root_run_id)
        children = list((await session.execute(
            select(AgentFlowRun).where(AgentFlowRun.parent_run_id == root_run_id)
        )).scalars().all())
        edges = list((await session.execute(select(AgentFlowRunEdge))).scalars().all())

    assert root.status == "completed"
    assert len(children) == 1
    assert children[0].status == "completed"
    assert children[0].root_run_id == root_run_id
    assert children[0].run_depth == 1
    assert children[0].input_payload == {"topic": "AI governance"}
    assert children[0].governance_context["inherited"] is True
    assert len(edges) == 1
    assert edges[0].status == "completed"
    assert str(children[0].id) in root.result_summary[str(parent_node_id)]


@pytest.mark.asyncio
async def test_runtime_blocks_cycle_to_ancestor(flow_sessions):
    root_flow_id = uuid.uuid4()
    child_flow_id = uuid.uuid4()
    root_run_id = uuid.uuid4()
    child_run_id = uuid.uuid4()

    async with flow_sessions() as session:
        root_flow = AgentFlow(id=root_flow_id, name="Root", schedule_config={}, viewport={})
        child_flow = AgentFlow(id=child_flow_id, name="Child", schedule_config={}, viewport={})
        root_run = AgentFlowRun(
            id=root_run_id,
            flow_id=root_flow_id,
            root_run_id=root_run_id,
            status="running",
            node_states={},
            result_summary={},
        )
        child_run = AgentFlowRun(
            id=child_run_id,
            flow_id=child_flow_id,
            root_run_id=root_run_id,
            parent_run_id=root_run_id,
            run_depth=1,
            status="running",
            node_states={},
            result_summary={},
        )
        session.add_all([root_flow, child_flow, root_run, child_run])
        await session.commit()

        with pytest.raises(ValueError, match="cycle detected"):
            await flow_engine._validate_child_safety(session, child_run, root_flow)


@pytest.mark.asyncio
async def test_stack_builder_generates_normal_sequential_flow(flow_sessions):
    async with flow_sessions() as session:
        first = AgentFlow(
            name="Research",
            schedule_config={},
            viewport={},
            version=2,
            allow_as_subflow=True,
            required_tools=["workspace"],
        )
        second = AgentFlow(
            name="Report",
            schedule_config={},
            viewport={},
            version=4,
            allow_as_subflow=True,
            required_tools=["office"],
        )
        session.add_all([first, second])
        await session.flush()

        response = await create_flow_stack(
            FlowStackCreate(
                name="Research to Report",
                flow_ids=[first.id, second.id],
                version_mode="locked",
            ),
            AgentFlowService(session),
            session,
        )
        await session.commit()

    stack = response.data
    assert stack.flow_type == "stack"
    assert [node.node_type for node in stack.nodes] == ["input", "subflow", "subflow", "output"]
    subflows = [node for node in stack.nodes if node.node_type == "subflow"]
    assert [node.config["child_flow_version"] for node in subflows] == [2, 4]
    assert len(stack.edges) == 3
    assert stack.required_tools == ["office", "workspace"]


@pytest.mark.asyncio
async def test_execution_tree_api_returns_nested_children(flow_sessions):
    flow_id = uuid.uuid4()
    root_run_id = uuid.uuid4()
    child_run_id = uuid.uuid4()
    async with flow_sessions() as session:
        flow = AgentFlow(id=flow_id, name="Tree Flow", schedule_config={}, viewport={})
        root = AgentFlowRun(
            id=root_run_id,
            flow_id=flow_id,
            root_run_id=root_run_id,
            status="completed",
            node_states={},
            result_summary={},
        )
        child = AgentFlowRun(
            id=child_run_id,
            flow_id=flow_id,
            root_run_id=root_run_id,
            parent_run_id=root_run_id,
            run_depth=1,
            status="completed",
            trigger_type="subflow",
            node_states={},
            result_summary={},
        )
        session.add_all([flow, root, child])
        await session.commit()

        response = await get_run_tree(root_run_id, session)

    assert response.data["run_id"] == str(root_run_id)
    assert response.data["children"][0]["run_id"] == str(child_run_id)
    assert response.data["children"][0]["run_depth"] == 1


@pytest.mark.asyncio
async def test_child_timeout_cancels_child_run(flow_sessions, monkeypatch):
    parent_flow_id = uuid.uuid4()
    child_flow_id = uuid.uuid4()
    parent_run_id = uuid.uuid4()
    parent_node_id = uuid.uuid4()

    async with flow_sessions() as session:
        session.add_all([
            AgentFlow(id=parent_flow_id, name="Parent", schedule_config={}, viewport={}),
            AgentFlow(
                id=child_flow_id,
                name="Slow Child",
                schedule_config={},
                viewport={},
                allow_as_subflow=True,
            ),
            AgentFlowRun(
                id=parent_run_id,
                flow_id=parent_flow_id,
                root_run_id=parent_run_id,
                status="running",
                node_states={},
                result_summary={},
                governance_context={"permissions": {}},
            ),
        ])
        await session.commit()

    async def slow_execute(_run_id, _flow_id):
        await asyncio.sleep(30)

    monkeypatch.setattr(flow_engine, "_execute_flow", slow_execute)
    with pytest.raises(ValueError, match="timed out"):
        await flow_engine.execute_child_flow(
            parent_run_id,
            parent_node_id,
            child_flow_id,
            {},
            flow_engine.ChildFlowExecutionOptions(timeout_seconds=0.01),
            {"permissions": {}},
        )

    async with flow_sessions() as session:
        child = (await session.execute(
            select(AgentFlowRun).where(AgentFlowRun.parent_run_id == parent_run_id)
        )).scalar_one()
    assert child.status == "cancelled"
    assert "timed out" in child.error_message
