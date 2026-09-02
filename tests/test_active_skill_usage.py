from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.api.deps import get_db
from shogun.api.skills import router as skills_router
from shogun.config import settings
from shogun.db.base import Base
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.skill import Skill
from shogun.schemas.skills import SkillActivationRequest
from shogun.services import active_skill_service as module
from shogun.services.active_skill_service import (
    SkillActivationService,
    SkillCompatibilityService,
    SkillContextComposer,
    SkillEmbeddingService,
    SkillHierarchyService,
)
from shogun.services.native_skills import _execute_active_skill_tool


@pytest.fixture
async def skill_session(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(module.EventLogger, "emit", AsyncMock(return_value=str(uuid.uuid4())))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def make_skill(name: str, *, triggers=None, status="installed", exam="passed", priority=70, **kwargs):
    slug = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:6]}"
    return Skill(
        name=name,
        slug=slug,
        version="1.0.0",
        skill_type=kwargs.pop("skill_type", "instruction"),
        manifest={"description": f"Operational guidance for {name}"},
        status=status,
        exam_status=exam,
        tags=kwargs.pop("tags", triggers or []),
        triggers=triggers or [],
        use_when=kwargs.pop("use_when", triggers or []),
        avoid_when=kwargs.pop("avoid_when", []),
        requires_tools=kwargs.pop("requires_tools", []),
        minimum_posture=kwargs.pop("minimum_posture", "guarded"),
        risk_tier=kwargs.pop("risk_tier", "low"),
        priority=priority,
        max_context_tokens=kwargs.pop("max_context_tokens", 600),
        activation_mode=kwargs.pop("activation_mode", "advisory"),
        verification_checklist=kwargs.pop("verification_checklist", []),
        **kwargs,
    )


def test_skill_description_is_backed_by_manifest():
    skill = make_skill("Manifest Description")

    assert skill.description == "Operational guidance for Manifest Description"

    skill.description = "Updated operational guidance"

    assert skill.manifest["description"] == "Updated operational guidance"


@pytest.mark.asyncio
async def test_relevant_passed_skill_activates_and_failed_skill_is_blocked(skill_session):
    good = make_skill("Build Paper Writer", triggers=["build paper", "implementation spec"])
    failed = make_skill("Unsafe Writer", triggers=["build paper"], exam="failed", priority=100)
    skill_session.add_all([good, failed])
    await skill_session.flush()

    result = await SkillActivationService(skill_session).activate(
        SkillActivationRequest(
            run_id="chat-1",
            objective="Write a Shogun build paper and implementation spec",
            posture="campaign",
            available_tools=["chat"],
        )
    )

    assert [item["name"] for item in result["active_skills"]] == ["Build Paper Writer"]
    assert result["active_skills"][0]["brief"].startswith("ACTIVE SKILL")
    assert "Archives semantic memory was searched" in result["context_block"]
    assert "evaluated 2 available skills and injected the 1 most relevant" in result["context_block"]
    assert result["total_injected_tokens"] <= settings.active_skill_max_total_context_tokens
    assert any(
        item["name"] == "Unsafe Writer" and item["blocked_reason"] == "exam:failed" for item in result["blocked_skills"]
    )


@pytest.mark.asyncio
async def test_every_task_searches_archives_and_can_activate_achieved_skill(skill_session, monkeypatch):
    achieved = make_skill(
        "Incident Triage",
        triggers=["production incident", "triage"],
        status="available",
        exam="passed",
    )
    skill_session.add(achieved)
    await skill_session.flush()
    archive_search = AsyncMock(return_value={str(achieved.id): 0.97})
    monkeypatch.setattr(SkillEmbeddingService, "search", archive_search)

    result = await SkillActivationService(skill_session).activate(
        SkillActivationRequest(
            objective="Triage a production incident",
            context="The API is returning errors after deployment",
            posture="campaign",
            available_tools=["chat"],
        )
    )

    archive_search.assert_awaited_once()
    query = archive_search.await_args.args[0]
    assert "Triage a production incident" in query
    assert "API is returning errors" in query
    assert [item["name"] for item in result["active_skills"]] == ["Incident Triage"]


@pytest.mark.asyncio
async def test_runtime_injects_canonical_markdown_from_archives(skill_session, monkeypatch):
    skill = make_skill("Canonical Runbook", triggers=["canonical runbook"])
    skill.body_text = "STALE SKILL TABLE COPY"
    skill.brief_text = "STALE BRIEF"
    skill_session.add(skill)
    await skill_session.flush()
    skill_session.add(
        MemoryRecord(
            agent_id=uuid.uuid4(),
            memory_type="skills",
            source_ref_id=skill.id,
            source_type="dojo_skill",
            title="Skill: Canonical Runbook",
            content="# Real Skill\n\nFollow the golden Archive procedure.",
            is_pinned=True,
            decay_class="pinned",
            tags=[f"skill:{skill.slug}"],
        )
    )
    await skill_session.flush()
    monkeypatch.setattr(
        SkillEmbeddingService,
        "search",
        AsyncMock(return_value={str(skill.id): 0.99}),
    )

    result = await SkillActivationService(skill_session).activate(
        SkillActivationRequest(
            objective="Use the canonical runbook",
            posture="campaign",
            available_tools=["chat"],
        )
    )

    assert "CANONICAL ARCHIVES INSTRUCTIONS" in result["context_block"]
    assert "Follow the golden Archive procedure" in result["context_block"]
    assert "STALE BRIEF" not in result["context_block"]


@pytest.mark.asyncio
async def test_hybrid_retrieval_goes_from_specializations_and_bundles_to_skills(skill_session, monkeypatch):
    bundle_skill = make_skill("Rollback Orchestrator", triggers=[])
    bundle_skill.manifest = {**bundle_skill.manifest, "openclaw_id": "skill-bundle"}
    specialization_skill = make_skill("Autonomous Release Verifier", triggers=[])
    specialization_skill.manifest = {**specialization_skill.manifest, "openclaw_id": "skill-spec"}
    direct_skill = make_skill("Deployment Checklist", triggers=["deploy service"])
    direct_skill.manifest = {**direct_skill.manifest, "openclaw_id": "skill-direct"}
    skill_session.add_all([bundle_skill, specialization_skill, direct_skill])
    await skill_session.flush()

    monkeypatch.setattr(
        SkillHierarchyService,
        "_catalog",
        AsyncMock(return_value=(
            [{
                "id": "bundle-deploy",
                "name": "Autonomous Deployment Operations",
                "description": "Safe deployment, rollback, and release operations",
                "currentVersion": {"skills": [{"id": "skill-bundle", "name": "Rollback Orchestrator"}]},
            }],
            [{
                "id": "spec-automation",
                "name": "Autonomous Automation",
                "description": "Verify and deploy autonomous production automation",
                "requiredSkillIds": ["skill-spec"],
            }],
        )),
    )
    monkeypatch.setattr(
        SkillEmbeddingService,
        "search",
        AsyncMock(return_value={str(direct_skill.id): 0.95}),
    )

    result = await SkillActivationService(skill_session).activate(
        SkillActivationRequest(
            objective="Deploy an autonomous service with rollback verification",
            posture="campaign",
            available_tools=["chat"],
            max_skills=3,
        )
    )

    names = {item["name"] for item in result["active_skills"]}
    assert names == {"Rollback Orchestrator", "Autonomous Release Verifier", "Deployment Checklist"}
    assert result["retrieval"]["strategy"] == "hybrid_hierarchical_direct"
    assert result["retrieval"]["hierarchy_candidate_count"] == 2
    reasons = {item["name"]: item["activation_reason"] for item in result["active_skills"]}
    assert "bundle:" in reasons["Rollback Orchestrator"]
    assert "specialization:" in reasons["Autonomous Release Verifier"]


@pytest.mark.asyncio
async def test_conflict_group_keeps_highest_ranked_skill(skill_session):
    short = make_skill("Short Reply", triggers=["linkedin reply"], priority=90, conflict_group="writing_length")
    long = make_skill("Long Essay", triggers=["linkedin reply"], priority=20, conflict_group="writing_length")
    skill_session.add_all([short, long])
    await skill_session.flush()

    result = await SkillActivationService(skill_session).activate(
        SkillActivationRequest(objective="Create a LinkedIn reply", posture="campaign", available_tools=["chat"])
    )
    assert [item["name"] for item in result["active_skills"]] == ["Short Reply"]
    assert result["conflict_notes"] and "Long Essay suppressed" in result["conflict_notes"][0]


def test_posture_and_ide_tool_gates_are_deterministic():
    ronin = make_skill("Desktop Automation", triggers=["desktop"], minimum_posture="ronin", risk_tier="critical")
    request = SkillActivationRequest(objective="automate desktop", posture="campaign", available_tools=[])
    assert SkillCompatibilityService.blocked_reason(ronin, request) == "posture_requires:ronin"

    ide = make_skill(
        "Safe Patching",
        triggers=["patch code"],
        minimum_posture="campaign",
        risk_tier="medium",
        requires_tools=["ide.file.read", "ide.file.apply_patch"],
        activation_mode="tool_gated",
    )
    no_ide = SkillActivationRequest(
        objective="patch code",
        posture="campaign",
        available_tools=["ide.file.read", "ide.file.apply_patch"],
        ide_enabled=False,
    )
    assert SkillCompatibilityService.blocked_reason(ide, no_ide) == "ide_mode_disabled"
    assert SkillCompatibilityService.blocked_reason(ide, no_ide.model_copy(update={"ide_enabled": True})) is None


def test_context_composer_enforces_total_and_per_skill_token_budgets():
    first = make_skill("First", triggers=["first"], max_context_tokens=20)
    second = make_skill("Second", triggers=["second"], max_context_tokens=20)
    first.brief_text = "ACTIVE SKILL: First\n" + "procedure " * 100
    second.brief_text = "ACTIVE SKILL: Second\n" + "procedure " * 100
    selected = [{"skill": first}, {"skill": second}]
    block, used = SkillContextComposer.compose(selected, budget=30)
    assert used <= 30
    assert selected[0]["injected_tokens"] <= 20
    assert "ACTIVE SKILL" in block


@pytest.mark.asyncio
async def test_outcome_updates_run_and_skill_stats(skill_session):
    skill = make_skill("Verifier", triggers=["verify"])
    skill_session.add(skill)
    await skill_session.flush()
    result = await SkillActivationService(skill_session).activate(
        SkillActivationRequest(
            run_id="run-outcome", objective="verify the output", posture="guarded", available_tools=[]
        )
    )
    active_id = result["active_skills"][0]["active_skill_run_id"]
    record = await SkillActivationService(skill_session).outcome(active_id, "success", "Checklist passed")
    assert record.outcome == "success"
    assert record.outcome_summary == "Checklist passed"
    assert skill.success_count == 1


@pytest.mark.asyncio
async def test_defaults_seed_operational_validated_skills(skill_session):
    service = SkillActivationService(skill_session)
    await service.ensure_defaults()
    await skill_session.flush()
    result = await service.activate(
        SkillActivationRequest(
            objective="Write a complete Shogun implementation build paper",
            posture="campaign",
            available_tools=["chat", "agent_flow", "stacks"],
        )
    )
    names = {item["name"] for item in result["active_skills"]}
    assert "Build Paper Writer" in names
    assert "Shogun Architecture" in names
    agentflow_skill = (
        await skill_session.execute(select(Skill).where(Skill.slug == "agentflow-operator"))
    ).scalar_one()
    assert "Flow Stack is not part of Yellow Label" in agentflow_skill.body_text
    assert agentflow_skill.local_path.endswith("agentflow-operator\\SKILL.md") or agentflow_skill.local_path.endswith(
        "agentflow-operator/SKILL.md"
    )
    assert agentflow_skill.status == "installed"


@pytest.mark.asyncio
async def test_activation_and_run_detail_api(skill_session):
    skill = make_skill("API Writing Skill", triggers=["release note"])
    skill_session.add(skill)
    await skill_session.commit()
    app = FastAPI()
    app.include_router(skills_router, prefix="/api/v1")

    async def override_db():
        yield skill_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        activated = await client.post(
            "/api/v1/skills/activate",
            json={
                "run_id": "api-run-1",
                "objective": "Write a release note",
                "posture": "campaign",
                "available_tools": ["chat"],
            },
        )
        assert activated.status_code == 200
        assert activated.json()["data"]["active_skills"][0]["name"] == "API Writing Skill"
        detail = await client.get("/api/v1/skills/active-runs", params={"run_id": "api-run-1"})
        assert detail.status_code == 200
        assert detail.json()["data"][0]["skill_name"] == "API Writing Skill"


@pytest.mark.asyncio
async def test_agent_skill_tools_activate_then_retrieve_and_explain(skill_session, monkeypatch):
    from shogun.api import security as security_api

    skill = make_skill("Agent Pipeline Skill", triggers=["pipeline regression"])
    skill_session.add(skill)
    await skill_session.flush()
    monkeypatch.setattr(
        security_api,
        "_get_agent_posture",
        AsyncMock(return_value={"active_tier": "campaign", "ide_enabled": False}),
    )

    activated = json.loads(
        await _execute_active_skill_tool(
            "skills_request_activation",
            {"run_id": "agent-pipeline-run", "objective": "Run a pipeline regression"},
            skill_session,
        )
    )
    active = json.loads(
        await _execute_active_skill_tool("skills_get_active", {"run_id": "agent-pipeline-run"}, skill_session)
    )
    explained = json.loads(
        await _execute_active_skill_tool("skills_explain_active", {"run_id": "agent-pipeline-run"}, skill_session)
    )

    assert activated["status"] == "success"
    assert [item["name"] for item in activated["active_skills"]] == ["Agent Pipeline Skill"]
    assert active["total"] == 1
    assert active["active_skills"][0]["name"] == "Agent Pipeline Skill"
    assert explained["total"] == 1
    assert explained["active_skills"][0]["reason"]
