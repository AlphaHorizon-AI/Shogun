"""Focused contract tests for the durable Supermode runtime."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import shogun.db.models  # noqa: F401 - register every FK target in metadata
from shogun.api import control_plane_auth
from shogun.api.deps import get_db
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.agent_flow import AgentFlowEdge, AgentFlowNode
from shogun.db.models.mission import Mission
from shogun.db.models.samurai_profile import SamuraiProfile
from shogun.db.models.skill import Skill
from shogun.db.models.supermode import MissionAgent, MissionEvent, MissionPlan, MissionTask
from shogun.services import posture_guard
from shogun.services.active_skill_service import SkillEmbeddingService, SkillHierarchyService
from shogun.services.agent_service import AgentService
from shogun.services.posture_guard import ActiveSubagentUsage
from shogun.supermode import supervisor
from shogun.supermode import worker as mission_worker
from shogun.supermode.planner import create_initial_plan
from shogun.supermode.service import SupermodeMissionService
from shogun.supermode.state_machine import (
    InvalidMissionTransitionError,
    transition_mission,
)


@pytest.fixture
async def supermode_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def mission_record(*, status: str = "planning") -> Mission:
    return Mission(
        mission_type="supermode",
        title="Verify the durable mission runtime",
        description="Test mission",
        status=status,
        priority="medium",
        requested_by="test",
        input_payload={},
        is_supermode=True,
        owner_user_id="test",
        objective="Build and validate a robust software system",
        objective_original="Build and validate a robust software system",
        governance_snapshot={"active_tier": "campaign"},
        max_agents=3,
        max_total_agents=8,
        max_parallel_agents=3,
    )


def test_supermode_accepts_ordinary_language_confidence_scores():
    assert mission_worker._normalized_score("High", 0.6) == 0.8
    assert mission_worker._normalized_score("75%", 0.6) == 0.75
    assert mission_worker._normalized_score("not scored", 0.6) == 0.6


@pytest.mark.asyncio
async def test_state_machine_persists_transitions_and_rejects_illegal_restart(
    supermode_session_factory,
):
    async with supermode_session_factory() as session:
        mission = mission_record()
        session.add(mission)
        await session.flush()

        await transition_mission(session, mission, "running", reason="Plan ready")
        await transition_mission(session, mission, "paused_budget", reason="Budget reached")
        await session.commit()

        events = list(
            (
                await session.scalars(
                    select(MissionEvent)
                    .where(MissionEvent.mission_id == mission.id)
                    .order_by(MissionEvent.created_at)
                )
            ).all()
        )
        assert mission.status == "paused_budget"
        assert [event.event_type for event in events] == ["MISSION_RUNNING", "MISSION_PAUSED_BUDGET"]

        mission.status = "completed"
        with pytest.raises(InvalidMissionTransitionError):
            await transition_mission(session, mission, "running", reason="Illegal restart")


@pytest.mark.asyncio
async def test_planner_creates_normalized_parallel_graph(supermode_session_factory):
    async with supermode_session_factory() as session:
        mission = mission_record()
        session.add(mission)
        await session.flush()

        plan = await create_initial_plan(session, mission)
        await session.commit()

        agents = list(
            (await session.scalars(select(MissionAgent).where(MissionAgent.mission_id == mission.id))).all()
        )
        tasks = list(
            (await session.scalars(select(MissionTask).where(MissionTask.mission_id == mission.id))).all()
        )
        plans = list(
            (await session.scalars(select(MissionPlan).where(MissionPlan.mission_id == mission.id))).all()
        )

        assert plan.version == mission.current_plan_version == 1
        assert len(plans) == 1
        assert len(agents) == mission.max_agents
        assert len(tasks) == 4
        assert sum(task.status == "ready" for task in tasks) == 2
        assert all(task.assigned_agent_id for task in tasks)
        assert any(len(task.depends_on_task_ids) == 2 for task in tasks)


@pytest.mark.asyncio
async def test_ordinary_commercial_mission_uses_compact_three_stage_graph(supermode_session_factory):
    async with supermode_session_factory() as session:
        mission = mission_record()
        mission.objective = (
            "Prepare a detailed competitor analysis, a customer communications plan for Fyn, and a solid GTM."
        )
        mission.objective_original = mission.objective
        session.add(mission)
        await session.flush()

        await create_initial_plan(session, mission)
        await session.commit()

        agents = list(
            (await session.scalars(select(MissionAgent).where(MissionAgent.mission_id == mission.id))).all()
        )
        tasks = list(
            (await session.scalars(select(MissionTask).where(MissionTask.mission_id == mission.id))).all()
        )
        synthesis = next(task for task in tasks if task.task_type == "mission_synthesis")

        assert len(agents) == 3
        assert len(tasks) == 3
        assert len(synthesis.depends_on_task_ids) == 2
        assert "Review, synthesize" in synthesis.title
        assert all(task.max_retries == 1 for task in tasks)


@pytest.mark.asyncio
async def test_planner_prefers_skill_matched_fleet_samurai_and_preserves_provenance(
    supermode_session_factory,
):
    async with supermode_session_factory() as session:
        skill = Skill(
            name="Evidence Research",
            slug="evidence-research",
            version="1.0.0",
            skill_type="instruction",
            manifest={"description": "Find primary sources and validate evidence"},
            status="installed",
            exam_status="passed",
            tags=["research", "evidence", "primary sources"],
            triggers=["evidence base", "research"],
            use_when=["find defensible facts"],
            priority=90,
        )
        fleet_agent = Agent(
            agent_type="samurai",
            name="Akira Evidence Scout",
            slug="akira-evidence-scout",
            description="A fleet researcher specializing in defensible primary-source evidence.",
            status="active",
            tags=["research", "evidence"],
        )
        session.add_all([skill, fleet_agent])
        await session.flush()
        session.add(
            SamuraiProfile(
                agent_id=fleet_agent.id,
                role="Research Analyst",
                specializations=["primary source research", "evidence review"],
                assigned_skill_ids=[str(skill.id)],
                max_parallel_jobs=1,
            )
        )
        mission = mission_record()
        mission.governance_snapshot = {
            "active_tier": "campaign",
            "spawn_capacity_at_creation": 1,
        }
        session.add(mission)
        await session.flush()

        await create_initial_plan(session, mission)
        await session.commit()

        routed = await session.scalar(
            select(MissionAgent).where(
                MissionAgent.mission_id == mission.id,
                MissionAgent.source_type == "fleet",
            )
        )
        event = await session.scalar(
            select(MissionEvent).where(
                MissionEvent.mission_id == mission.id,
                MissionEvent.event_type == "AGENT_ROUTED_FROM_FLEET",
            )
        )
        assert routed is not None
        assert routed.fleet_agent_id == fleet_agent.id
        assert routed.role_name == "Akira Evidence Scout"
        assert routed.inherited_skill_ids == [str(skill.id)]
        assert routed.inherited_skill_names == ["Evidence Research"]
        assert routed.routing_preferences["mission_role"] == "Lead Researcher"
        assert "matched assigned skills" in routed.agent_routing_reason
        assert event is not None
        assert event.event_data["source_type"] == "fleet"
        assert int(
            (
                await session.scalar(
                    select(func.count(MissionAgent.id)).where(
                        MissionAgent.mission_id == mission.id,
                        MissionAgent.source_type == "spawned",
                    )
                )
            )
            or 0
        ) == 1


@pytest.mark.asyncio
async def test_fleet_profile_accepts_only_validated_shogun_skills(supermode_session_factory):
    async with supermode_session_factory() as session:
        valid = Skill(
            name="Validated Skill",
            slug="validated-skill",
            version="1.0.0",
            skill_type="instruction",
            manifest={"description": "Validated procedure"},
            status="installed",
            exam_status="passed",
        )
        blocked = Skill(
            name="Blocked Skill",
            slug="blocked-skill",
            version="1.0.0",
            skill_type="instruction",
            manifest={"description": "Disabled procedure"},
            status="disabled",
            exam_status="passed",
        )
        agent = Agent(
            agent_type="samurai",
            name="Fleet Operator",
            slug="fleet-operator",
            status="active",
        )
        session.add_all([valid, blocked, agent])
        await session.flush()

        profile = await AgentService(session).update_samurai_profile(
            agent.id,
            role="Operator",
            assigned_skill_ids=[valid.id],
        )
        assert profile.assigned_skill_ids == [str(valid.id)]
        with pytest.raises(ValueError, match="validated active skillset"):
            await AgentService(session).update_samurai_profile(
                agent.id,
                assigned_skill_ids=[blocked.id],
            )


@pytest.mark.asyncio
async def test_fleet_skill_catalog_and_assignment_api(
    api_app,
    client,
    supermode_session_factory,
    monkeypatch,
):
    async with supermode_session_factory() as session:
        skill = Skill(
            name="Fleet API Skill",
            slug="fleet-api-skill",
            version="1.0.0",
            skill_type="instruction",
            manifest={"description": "A validated fleet capability"},
            status="installed",
            exam_status="passed",
        )
        agent = Agent(
            agent_type="samurai",
            name="Fleet API Samurai",
            slug="fleet-api-samurai",
            status="active",
        )
        session.add_all([skill, agent])
        await session.commit()
        skill_id = skill.id
        agent_id = agent.id

    async def session_override():
        async with supermode_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    api_app.dependency_overrides[get_db] = session_override
    monkeypatch.setattr(control_plane_auth.settings, "infrastructure_admin_token", "fleet-skill-test-token")
    headers = {"X-Shogun-Infrastructure-Token": "fleet-skill-test-token"}
    try:
        catalog = await client.get("/api/v1/agents/samurai-skill-catalog", headers=headers)
        assert catalog.status_code == 200, catalog.text
        assert [item["name"] for item in catalog.json()["data"]] == ["Fleet API Skill"]

        assigned = await client.put(
            f"/api/v1/agents/{agent_id}/samurai-profile",
            headers=headers,
            json={"role": "API Operator", "assigned_skill_ids": [str(skill_id)]},
        )
        assert assigned.status_code == 200, assigned.text
        assert assigned.json()["data"]["assigned_skill_ids"] == [str(skill_id)]

        detail = await client.get(f"/api/v1/agents/{agent_id}", headers=headers)
        assert detail.status_code == 200, detail.text
        assert detail.json()["data"]["samurai_profile"]["assigned_skill_ids"] == [str(skill_id)]
    finally:
        api_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_fleet_samurai_activates_operator_selected_skill(
    supermode_session_factory,
    monkeypatch,
):
    async def no_semantic_results(*_args, **_kwargs):
        return {}

    async def no_hierarchy_results(*_args, **_kwargs):
        return {"boosts": {}, "paths": {}, "matched_bundles": [], "matched_specializations": []}

    monkeypatch.setattr(SkillEmbeddingService, "search", no_semantic_results)
    monkeypatch.setattr(SkillHierarchyService, "search", no_hierarchy_results)

    async with supermode_session_factory() as session:
        skill = Skill(
            name="Mission Verification",
            slug="mission-verification",
            version="1.0.0",
            skill_type="verification",
            manifest={"description": "Verify mission evidence before handoff"},
            status="installed",
            exam_status="passed",
            brief_text="ACTIVE SKILL: Mission Verification\nVerify every material claim.",
            triggers=["verify mission evidence"],
            priority=100,
        )
        mission = mission_record(status="running")
        session.add_all([skill, mission])
        await session.flush()
        agent = MissionAgent(
            mission_id=mission.id,
            source_type="fleet",
            role_name="Fleet Verifier",
            role_description="Validates evidence",
            objective="Verify the mission",
            status="active",
            spawn_reason="Fleet match",
            inherited_skill_ids=[str(skill.id)],
            inherited_skill_names=[skill.name],
        )
        session.add(agent)
        await session.flush()
        task = MissionTask(
            mission_id=mission.id,
            title="Verify evidence",
            objective="Verify mission evidence",
            task_type="mission_critique",
            status="running",
            assigned_agent_id=agent.id,
        )
        session.add(task)
        await session.flush()

        activation = await mission_worker._activate_agent_skills(
            session,
            mission,
            task,
            agent,
            {"active_tier": "campaign", "ide_enabled": False},
            [],
            "{}",
        )

        assert [item["name"] for item in activation["active_skills"]] == ["Mission Verification"]
        assert "Verify every material claim" in activation["context_block"]
        assert await session.scalar(
            select(MissionEvent).where(
                MissionEvent.mission_id == mission.id,
                MissionEvent.event_type == "SKILLS_ACTIVATED",
            )
        ) is not None


@pytest.mark.asyncio
async def test_agentflow_candidate_is_draft_and_preserves_parallel_dependencies(
    supermode_session_factory,
):
    async with supermode_session_factory() as session:
        mission = mission_record(status="completed")
        session.add(mission)
        await session.flush()
        await create_initial_plan(session, mission)
        flow = await SupermodeMissionService(session).create_agentflow_candidate(mission)
        await session.commit()

        nodes = list(
            (await session.scalars(select(AgentFlowNode).where(AgentFlowNode.flow_id == flow.id))).all()
        )
        edges = list(
            (await session.scalars(select(AgentFlowEdge).where(AgentFlowEdge.flow_id == flow.id))).all()
        )
        input_node = next(node for node in nodes if node.node_type == "input")
        outgoing_from_input = [edge for edge in edges if edge.source_node_id == input_node.id]

        assert flow.status == "draft"
        assert flow.template_source == "supermode"
        assert mission.agentflow_id == flow.id
        assert len(outgoing_from_input) == 2
        assert len(edges) == 6


@pytest.mark.asyncio
async def test_stale_leases_recover_after_restart(supermode_session_factory, monkeypatch):
    async with supermode_session_factory() as session:
        mission = mission_record(status="running")
        session.add(mission)
        await session.flush()
        agent = MissionAgent(
            mission_id=mission.id,
            role_name="Recovery Specialist",
            role_description="Exercises lease recovery",
            objective="Recover a bounded task",
            status="active",
            spawn_reason="Test recovery",
        )
        session.add(agent)
        await session.flush()
        task = MissionTask(
            mission_id=mission.id,
            title="Recover me",
            objective="Verify restart safety",
            status="running",
            assigned_agent_id=agent.id,
            lease_owner="dead-worker",
            lease_expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            retry_count=0,
        )
        session.add(task)
        await session.commit()
        task_id = task.id
        agent_id = agent.id

    monkeypatch.setattr(supervisor, "async_session_factory", supermode_session_factory)
    assert await supervisor.recover_stale_tasks() == 1

    async with supermode_session_factory() as session:
        recovered_task = await session.get(MissionTask, task_id)
        recovered_agent = await session.get(MissionAgent, agent_id)
        assert recovered_task.status == "ready"
        assert recovered_task.retry_count == 1
        assert recovered_task.lease_owner is None
        assert recovered_agent.status == "waiting"
        event = await session.scalar(
            select(MissionEvent).where(
                MissionEvent.mission_id == recovered_task.mission_id,
                MissionEvent.event_type == "TASK_RETRIED",
            )
        )
        assert event is not None


@pytest.mark.asyncio
async def test_scheduler_ticks_drive_a_mission_to_durable_completion(
    supermode_session_factory,
    monkeypatch,
):
    async with supermode_session_factory() as session:
        mission = mission_record()
        session.add(mission)
        await session.commit()
        mission_id = mission.id

    async def posture():
        return {
            "active_tier": "campaign",
            "supermode_enabled": True,
            "kill_switch_active": False,
        }

    async def complete_claimed_task(task_id):
        async with supermode_session_factory() as session:
            task = await session.get(MissionTask, task_id)
            task.status = "completed"
            task.task_summary = f"Validated result for {task.title}"
            task.output_payload = {"summary": task.task_summary}
            task.completed_at = datetime.now(timezone.utc)
            task.lease_owner = None
            task.lease_expires_at = None
            if task.task_type == "mission_synthesis":
                mission = await session.get(Mission, task.mission_id)
                mission.final_answer = task.task_summary
            await session.commit()

    monkeypatch.setattr(supervisor, "async_session_factory", supermode_session_factory)
    monkeypatch.setattr(supervisor, "run_claimed_task", complete_claimed_task)
    monkeypatch.setattr(mission_worker, "async_session_factory", supermode_session_factory)
    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", posture)

    for _ in range(3):
        await supervisor.supervisor_tick()

    async with supermode_session_factory() as session:
        mission = await session.get(Mission, mission_id)
        tasks = list(
            (await session.scalars(select(MissionTask).where(MissionTask.mission_id == mission_id))).all()
        )
        completed_event = await session.scalar(
            select(MissionEvent).where(
                MissionEvent.mission_id == mission_id,
                MissionEvent.event_type == "MISSION_COMPLETED",
            )
        )
        assert mission.status == "completed"
        assert mission.progress_percent == 100.0
        assert mission.agentflow_candidate["ready"] is True
        assert all(task.status == "completed" for task in tasks)
        assert completed_event is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("tier", ["campaign", "ronin"])
async def test_supermode_gate_allows_only_elevated_postures(monkeypatch, tier):
    async def posture():
        return {"active_tier": tier, "supermode_enabled": True}

    async def kill_switch():
        return None

    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", posture)
    monkeypatch.setattr(posture_guard, "check_kill_switch", kill_switch)
    result = await posture_guard.check_supermode_access()
    assert result["active_tier"] == tier


@pytest.mark.asyncio
async def test_supermode_gate_rejects_tactical_even_if_ui_is_bypassed(monkeypatch):
    async def posture():
        return {"active_tier": "tactical", "supermode_enabled": False}

    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", posture)
    with pytest.raises(HTTPException) as error:
        await posture_guard.check_supermode_access()
    assert error.value.status_code == 403


@pytest.mark.asyncio
async def test_create_api_persists_mission_and_creation_event(
    api_app,
    client,
    supermode_session_factory,
    monkeypatch,
):
    async def session_override():
        async with supermode_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def access():
        return {
            "active_tier": "campaign",
            "max_active_subagents": 6,
            "supermode_enabled": True,
        }

    async def usage():
        return ActiveSubagentUsage(permanent=0, mission=0)

    api_app.dependency_overrides[get_db] = session_override
    monkeypatch.setattr(posture_guard, "check_supermode_access", access)
    monkeypatch.setattr(posture_guard, "get_active_subagent_usage", usage)
    monkeypatch.setattr(control_plane_auth.settings, "infrastructure_admin_token", "supermode-test-token")
    try:
        response = await client.post(
            "/api/v1/supermode/missions",
            headers={"X-Shogun-Infrastructure-Token": "supermode-test-token"},
            json={
                "objective": "Research and validate a production-ready software rollout",
                "success_criteria": ["Produce a validated rollout plan"],
            },
        )
        assert response.status_code == 201, response.text
        payload = response.json()["data"]
        assert payload["status"] == "planning"
        assert payload["posture_at_creation"] == "campaign"
        assert payload["mission_control_url"] == f"/chat?tab=mission-control&mission={payload['id']}"

        async with supermode_session_factory() as session:
            mission = await session.get(Mission, payload["id"])
            event = await session.scalar(
                select(MissionEvent).where(
                    MissionEvent.mission_id == mission.id,
                    MissionEvent.event_type == "MISSION_CREATED",
                )
            )
        assert mission.is_supermode is True
        assert event is not None

        active_delete = await client.delete(
            f"/api/v1/supermode/missions/{payload['id']}",
            headers={"X-Shogun-Infrastructure-Token": "supermode-test-token"},
        )
        assert active_delete.status_code == 409

        paused = await client.post(
            f"/api/v1/supermode/missions/{payload['id']}/pause",
            headers={"X-Shogun-Infrastructure-Token": "supermode-test-token"},
            json={},
        )
        assert paused.status_code == 200, paused.text
        assert paused.json()["data"]["status"] == "paused"

        persisted_pause = await client.get(
            f"/api/v1/supermode/missions/{payload['id']}",
            headers={"X-Shogun-Infrastructure-Token": "supermode-test-token"},
        )
        assert persisted_pause.json()["data"]["status"] == "paused"

        resumed = await client.post(
            f"/api/v1/supermode/missions/{payload['id']}/resume",
            headers={"X-Shogun-Infrastructure-Token": "supermode-test-token"},
            json={},
        )
        assert resumed.status_code == 200, resumed.text
        assert resumed.json()["data"]["status"] == "planning"

        stopped = await client.post(
            f"/api/v1/supermode/missions/{payload['id']}/cancel",
            headers={"X-Shogun-Infrastructure-Token": "supermode-test-token"},
            json={},
        )
        assert stopped.status_code == 200, stopped.text
        assert stopped.json()["data"]["status"] == "cancelled"

        async with supermode_session_factory() as session:
            control_events = set(
                (
                    await session.scalars(
                        select(MissionEvent.event_type).where(
                            MissionEvent.mission_id == payload["id"],
                            MissionEvent.event_type.in_(
                                ["MISSION_PAUSED", "MISSION_RESUMED", "MISSION_CANCELLED"]
                            ),
                        )
                    )
                ).all()
            )
            assert control_events == {"MISSION_PAUSED", "MISSION_RESUMED", "MISSION_CANCELLED"}

        deleted = await client.delete(
            f"/api/v1/supermode/missions/{payload['id']}",
            headers={"X-Shogun-Infrastructure-Token": "supermode-test-token"},
        )
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["data"] == {
            "deleted": True,
            "mission_id": payload["id"],
            "artifacts_retained": True,
        }

        async with supermode_session_factory() as session:
            assert await session.get(Mission, payload["id"]) is None
            assert await session.scalar(
                select(MissionEvent).where(MissionEvent.mission_id == payload["id"])
            ) is None
    finally:
        api_app.dependency_overrides.clear()
