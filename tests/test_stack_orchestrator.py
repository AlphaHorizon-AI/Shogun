from __future__ import annotations

import asyncio
import json
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
from shogun.services.stack_orchestrator import (
    StackCompactionService,
    StackOrchestratorService,
    StackVerificationService,
    build_published_stack_output,
)


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
async def test_selected_stack_inherits_saved_output_publication(stack_sessions):
    stack_id, _ = await _seed_stack(stack_sessions, child_count=1)
    async with stack_sessions() as session:
        flow = await session.get(AgentFlow, stack_id)
        flow.schedule_config = {"stack_orchestrator": {"output_publication": "summary_only"}}
        await session.commit()
        run = await StackOrchestratorService(session).create(
            StackOrchestratorCreate(
                mode="selected_stack",
                selected_stack_id=stack_id,
                objective="Use the saved handover publication policy",
            )
        )

    assert run.output_publication == "summary_only"


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
    assert current.output_publication == "summary_and_final"
    assert set(current.published_output) == {"summary", "final_output"}
    assert "step_outputs" not in current.published_output
    assert steps[0].output_json["publication"] == "handover_only"
    assert steps[-1].output_json["publication"] == "final"
    assert steps[1].input_json == steps[0].output_json["output"]
    assert len(tree["children"]) == 2


@pytest.mark.parametrize(
    ("publication", "expected_keys"),
    [
        ("summary_only", {"summary"}),
        ("final_only", {"final_output"}),
        ("all_steps", {"summary", "step_outputs", "final_output"}),
    ],
)
def test_stack_output_publication_controls_visible_package(publication, expected_keys):
    stack = StackRun(
        mode="selected_stack",
        status="completed",
        objective="Publish only the selected stack package",
        posture="campaign",
        output_publication=publication,
    )
    steps = [
        StackStepRun(
            stack_run_id=uuid.uuid4(), step_id=f"step_{index:03d}", sequence=index,
            name=f"Flow {index}", status="completed",
            output_json={"output": {"result": f"result {index}"}},
        )
        for index in (1, 2)
    ]
    package = build_published_stack_output(stack, steps, {"status": "completed"})

    assert set(package) == expected_keys
    if publication == "all_steps":
        assert len(package["step_outputs"]) == 2
    if "final_output" in package:
        assert package["final_output"] == {"result": "result 2"}


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


@pytest.mark.asyncio
async def test_independent_verifier_rejects_explicit_failed_evidence(stack_sessions, monkeypatch):
    monkeypatch.setattr(StackVerificationService, "_semantic_judgement", AsyncMock(return_value=None))
    async with stack_sessions() as session:
        stack = StackRun(
            mode="selected_stack", status="running", objective="Ship a verified change", posture="campaign",
            success_criteria=["Tests pass"], metadata_json={},
        )
        session.add(stack)
        await session.flush()
        step = StackStepRun(
            stack_run_id=stack.id, step_id="step_001", sequence=1, name="Implement and test",
            status="running", expected_output="Working implementation with passing tests",
        )
        flow = AgentFlow(name="Verifier fixture", status="active", schedule_config={}, viewport={})
        session.add_all([step, flow])
        await session.flush()
        flow_run = AgentFlowRun(
            flow_id=flow.id, flow_version=1, root_run_id=uuid.uuid4(), status="completed",
            trigger_type="stack_orchestrator", node_states={}, result_summary={}, input_payload={},
            output_payload={"result": "implemented", "tests": [{"name": "unit tests", "status": "failed"}]},
            artifacts=[], governance_context={},
        )
        session.add(flow_run)
        await session.flush()
        verification = await StackVerificationService.verify(session, stack, step, flow_run)

    assert verification.status == "failed"
    assert verification.verification_type == "independent_quality_gate"
    assert any(item["name"] == "unit tests" and not item["passed"] for item in verification.metadata_json["checks"])


@pytest.mark.asyncio
async def test_final_step_cannot_claim_success_without_acceptance_evidence(stack_sessions, monkeypatch):
    monkeypatch.setattr(StackVerificationService, "_semantic_judgement", AsyncMock(return_value=None))
    async with stack_sessions() as session:
        flow = AgentFlow(name="Evidence fixture", status="active", schedule_config={}, viewport={})
        stack = StackRun(
            mode="selected_stack", status="running", objective="Prove the result", posture="campaign",
            success_criteria=["The requested behavior is demonstrated"], metadata_json={},
        )
        session.add_all([flow, stack])
        await session.flush()
        step = StackStepRun(
            stack_run_id=stack.id, step_id="step_001", sequence=1, name="Final delivery",
            status="running", expected_output="Verified delivery",
        )
        session.add(step)
        await session.flush()
        flow_run = AgentFlowRun(
            flow_id=flow.id, flow_version=1, root_run_id=uuid.uuid4(), status="completed",
            trigger_type="stack_orchestrator", node_states={}, result_summary={}, input_payload={},
            output_payload={"result": "done"}, artifacts=[], governance_context={},
        )
        session.add(flow_run)
        await session.flush()
        verification = await StackVerificationService.verify(session, stack, step, flow_run)

    assert verification.status == "failed"
    evidence_check = next(
        item for item in verification.metadata_json["checks"] if item["name"] == "success_criteria_evidence_present"
    )
    assert evidence_check["passed"] is False


def test_context_compaction_is_structured_and_budgeted(monkeypatch):
    monkeypatch.setattr(orchestrator_module.settings, "stack_orchestrator_context_budget_chars", 2400)
    stack = StackRun(
        mode="selected_stack", status="running", objective="Maintain continuity", posture="campaign",
        success_criteria=["Preserve decisions"], metadata_json={"decisions": ["Use the durable contract"]},
    )
    steps = [
        StackStepRun(
            stack_run_id=uuid.uuid4(), step_id=f"step_{index:03d}", sequence=index, name=f"Step {index}",
            status="completed", verification_status="passed", output_json={"output": {"detail": "x" * 1800}},
        )
        for index in range(1, 8)
    ]
    next_step = StackStepRun(
        stack_run_id=uuid.uuid4(), step_id="step_008", sequence=8, name="Continue safely", status="pending",
        expected_output="Verified final result",
    )
    steps.append(next_step)

    compacted = StackCompactionService.compact(stack, steps, next_step)
    payload = json.loads(compacted)

    assert len(compacted) <= 2400
    assert payload["continuity_version"] == 2
    assert payload["next_action"]["step_id"] == "step_008"
    assert payload["important_decisions"] == ["Use the durable contract"]


@pytest.mark.asyncio
async def test_recovery_resets_orphaned_child_run_to_checkpoint_boundary(stack_sessions, monkeypatch):
    stack_id, child_ids = await _seed_stack(stack_sessions, child_count=1)
    async with stack_sessions() as session:
        service = StackOrchestratorService(session)
        stack = await service.create(StackOrchestratorCreate(
            mode="selected_stack", selected_stack_id=stack_id, objective="Recover after restart",
        ))
        stack.status = "running"
        _, steps = await service.get(stack.id)
        orphan = AgentFlowRun(
            flow_id=child_ids[0], flow_version=1, root_run_id=uuid.uuid4(), status="running",
            trigger_type="stack_orchestrator", node_states={}, result_summary={}, input_payload={},
            output_payload={}, artifacts=[], governance_context={},
        )
        session.add(orphan)
        await session.flush()
        steps[0].status = "running"
        steps[0].flow_run_id = orphan.id
        await session.commit()
        await service._prepare_recovery(stack)
        await session.commit()
        recovered_step = await session.get(StackStepRun, steps[0].id)
        recovered_orphan = await session.get(AgentFlowRun, orphan.id)

    assert recovered_step.status == "pending"
    assert recovered_step.flow_run_id is None
    assert recovered_orphan.status == "cancelled"
    assert stack.metadata_json["recovery_events"][-1]["steps"] == ["step_001"]
