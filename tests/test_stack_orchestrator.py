from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.db.models.agent_flow import AgentFlow, AgentFlowEdge, AgentFlowNode
from shogun.db.models.agent_flow_run import AgentFlowRun, AgentFlowRunEdge
from shogun.db.models.stack_orchestrator import (
    StackArtifact,
    StackCheckpoint,
    StackRun,
    StackStepRun,
    StackVerification,
)
from shogun.engine import flow_engine
from shogun.schemas.stack_orchestrator import StackOrchestratorCreate, StackPlanDecision
from shogun.services import posture_guard
from shogun.services import stack_orchestrator as orchestrator_module
from shogun.services.stack_orchestrator import StackOrchestratorService


@pytest.fixture
async def stack_sessions(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        for table in (
            AgentFlow.__table__,
            AgentFlowNode.__table__,
            AgentFlowEdge.__table__,
            AgentFlowRun.__table__,
            AgentFlowRunEdge.__table__,
            StackRun.__table__,
            StackStepRun.__table__,
            StackCheckpoint.__table__,
            StackArtifact.__table__,
            StackVerification.__table__,
        ):
            await connection.run_sync(table.create)

    async def campaign_posture():
        return {
            "active_tier": "campaign",
            "kill_switch_active": False,
            "mado_enabled": True,
            "office_enabled": True,
            "ronin_enabled": False,
            "ide_enabled": True,
            "workspace_enabled": True,
        }

    monkeypatch.setattr(orchestrator_module, "async_session_factory", sessions)
    monkeypatch.setattr(flow_engine, "async_session_factory", sessions)
    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", campaign_posture)
    monkeypatch.setattr(posture_guard, "get_posture_permissions", campaign_posture)
    monkeypatch.setattr(orchestrator_module, "_audit", AsyncMock(return_value=None))

    yield sessions
    for task in list(orchestrator_module._active_stack_runs.values()):
        task.cancel()
    orchestrator_module._active_stack_runs.clear()
    await engine.dispose()


async def _seed_stack(sessions, child_count: int = 2) -> tuple[uuid.UUID, list[uuid.UUID]]:
    child_ids = [uuid.uuid4() for _ in range(child_count)]
    stack_id = uuid.uuid4()
    async with sessions() as session:
        stack = AgentFlow(
            id=stack_id,
            name="Coding Stack",
            flow_type="stack",
            status="active",
            schedule_config={},
            viewport={},
            required_tools=["workspace"],
        )
        session.add(stack)
        previous = None
        for index, child_id in enumerate(child_ids):
            child = AgentFlow(
                id=child_id,
                name=f"Step Flow {index + 1}",
                status="active",
                schedule_config={},
                viewport={},
                allow_as_subflow=True,
            )
            input_node = AgentFlowNode(
                id=uuid.uuid4(),
                flow_id=child_id,
                node_type="input",
                label="Input",
                position_x=0,
                position_y=0,
                config={"input_type": "api"},
            )
            stack_node = AgentFlowNode(
                id=uuid.uuid4(),
                flow_id=stack_id,
                node_type="subflow",
                label=f"Step {index + 1}",
                position_x=index * 250,
                position_y=0,
                config={"child_flow_id": str(child_id)},
            )
            session.add_all([child, input_node, stack_node])
            if previous:
                session.add(
                    AgentFlowEdge(
                        flow_id=stack_id,
                        source_node_id=previous,
                        target_node_id=stack_node.id,
                    )
                )
            previous = stack_node.id
        await session.commit()
    return stack_id, child_ids


@pytest.mark.asyncio
async def test_selected_stack_creates_persistent_step_plan(stack_sessions):
    stack_id, child_ids = await _seed_stack(stack_sessions)
    async with stack_sessions() as session:
        service = StackOrchestratorService(session)
        run = await service.create(
            StackOrchestratorCreate(
                mode="selected_stack",
                selected_stack_id=stack_id,
                objective="Run a governed coding stack",
                allowed_tools=["ide", "workspace"],
            )
        )
        run, steps = await service.get(run.id)

    assert run.status == "created"
    assert run.posture == "campaign"
    assert [step.flow_id for step in steps] == child_ids
    assert [step.step_id for step in steps] == ["step_001", "step_002"]


@pytest.mark.asyncio
async def test_template_mode_loads_long_running_program_controls(stack_sessions):
    async with stack_sessions() as session:
        service = StackOrchestratorService(session)
        run = await service.create(
            StackOrchestratorCreate(
                mode="template",
                stack_template_id="stack-program-01-enterprise",
                objective="Maintain an enterprise competitive intelligence watchtower",
            )
        )
        run, steps = await service.get(run.id)

    assert len(steps) == 8
    assert run.max_runtime_minutes == 1440
    assert run.max_iterations == 120
    assert run.max_retry_attempts_per_step == 3
    assert run.checkpoint_frequency == "after_each_subflow"
    assert run.verification_required is True
    assert run.failure_policy == "retry"


@pytest.mark.asyncio
async def test_goal_plan_requires_reviewed_stack_attachment(stack_sessions):
    stack_id, _ = await _seed_stack(stack_sessions, child_count=1)
    async with stack_sessions() as session:
        service = StackOrchestratorService(session)
        run = await service.create(
            StackOrchestratorCreate(
                mode="goal_driven",
                objective="Add a small verified feature",
                success_criteria=["Tests pass"],
            )
        )
        assert run.status == "waiting_approval"
        assert run.metadata_json["generated_plan"] is True
        run_id = run.id

        with pytest.raises(ValueError, match="attached"):
            await service.approve_plan(run_id, StackPlanDecision(approved=True))
        await session.rollback()
        await service.approve_plan(
            run_id,
            StackPlanDecision(approved=True, selected_stack_id=stack_id),
        )
        approved, steps = await service.get(run_id)

    assert approved.status == "created"
    assert approved.stack_id == stack_id
    assert len(steps) == 1
    assert steps[0].flow_id is not None


@pytest.mark.asyncio
async def test_stack_execution_checkpoints_verifies_and_summarizes(stack_sessions):
    stack_id, _ = await _seed_stack(stack_sessions)
    async with stack_sessions() as session:
        service = StackOrchestratorService(session)
        run = await service.create(
            StackOrchestratorCreate(
                mode="selected_stack",
                selected_stack_id=stack_id,
                objective="Execute and verify both reusable flows",
                failure_policy="fail_stack",
            )
        )
        await service.start(run.id)
        run_id = run.id

    for _ in range(100):
        await asyncio.sleep(0.03)
        async with stack_sessions() as session:
            current = await session.get(StackRun, run_id)
            if current.status in {"completed", "failed"}:
                break

    async with stack_sessions() as session:
        service = StackOrchestratorService(session)
        current, steps = await service.get(run_id)
        checkpoints = await service.checkpoints(run_id)
        artifacts = await service.artifacts(run_id)
        verifications = await service.verifications(run_id)
        tree = await service.tree(run_id)

    assert current.status == "completed"
    assert all(step.status == "completed" for step in steps)
    assert len(checkpoints) == 2
    assert len(artifacts) == 2
    assert len(verifications) == 2
    assert all(item.status == "passed" for item in verifications)
    assert current.final_summary["final_status"] == "completed"
    assert len(tree["children"]) == 2


@pytest.mark.asyncio
async def test_ide_and_ronin_permissions_are_never_inferred_from_posture(stack_sessions):
    with pytest.raises(ValueError, match="Ronin desktop"):
        StackOrchestratorService._validate_tools(
            ["desktop_control"],
            {"ronin_enabled": False},
            "campaign",
        )
    with pytest.raises(ValueError, match="IDE Mode"):
        StackOrchestratorService._validate_tools(
            ["vscode"],
            {"ide_enabled": False},
            "campaign",
        )


@pytest.mark.asyncio
async def test_pause_and_resume_continue_current_step_not_whole_stack(stack_sessions, monkeypatch):
    stack_id, _ = await _seed_stack(stack_sessions, child_count=1)
    original_execute = flow_engine._execute_flow

    async def slow_execute(_run_id, _flow_id):
        await asyncio.sleep(10)

    monkeypatch.setattr(flow_engine, "_execute_flow", slow_execute)
    async with stack_sessions() as session:
        service = StackOrchestratorService(session)
        run = await service.create(
            StackOrchestratorCreate(
                mode="selected_stack",
                selected_stack_id=stack_id,
                objective="Pause and resume safely",
            )
        )
        await service.start(run.id)
        run_id = run.id

    for _ in range(50):
        await asyncio.sleep(0.02)
        async with stack_sessions() as session:
            step = (await session.execute(select(StackStepRun).where(StackStepRun.stack_run_id == run_id))).scalar_one()
            if step.flow_run_id:
                break

    async with stack_sessions() as session:
        paused = await StackOrchestratorService(session).pause(run_id)
        _, paused_steps = await StackOrchestratorService(session).get(run_id)
    assert paused.status == "paused"
    assert paused_steps[0].status == "paused"

    monkeypatch.setattr(flow_engine, "_execute_flow", original_execute)
    async with stack_sessions() as session:
        await StackOrchestratorService(session).resume(run_id)

    for _ in range(100):
        await asyncio.sleep(0.03)
        async with stack_sessions() as session:
            current = await session.get(StackRun, run_id)
            if current.status in {"completed", "failed"}:
                break

    async with stack_sessions() as session:
        current, steps = await StackOrchestratorService(session).get(run_id)
    assert current.status == "completed"
    assert steps[0].status == "completed"
