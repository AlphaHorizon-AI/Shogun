from __future__ import annotations

import io
import json
import uuid
import zipfile
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.api.deps import get_db
from shogun.api.skills import router as skills_router
from shogun.db.base import Base
from shogun.db.models.skill import Skill
from shogun.db.models.skill_trajectory import (
    SkillCandidateRetrieval,
    SkillEpisode,
    SkillImprovementCandidate,
    SkillToolLink,
    SkillTrajectory,
    SkillVerificationLink,
)
from shogun.schemas.skills import SkillActivationRequest
from shogun.services.active_skill_service import SkillActivationService
from shogun.services.event_logger import EventLogger
from shogun.services.skill_trajectory_service import SkillTrajectoryExporter, SkillTrajectoryService


@pytest.fixture
async def trajectory_session(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    monkeypatch.setattr(EventLogger, "emit", AsyncMock(return_value=f"evt_{uuid.uuid4().hex}"))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def make_skill() -> Skill:
    return Skill(
        name="Trajectory Tester", slug=f"trajectory-tester-{uuid.uuid4().hex[:6]}", version="2.1.0",
        skill_type="instruction", manifest={"description": "Tests trajectory capture"},
        status="installed", exam_status="passed", tags=["trajectory"], triggers=["trajectory"],
        use_when=["trajectory evidence"], avoid_when=[], requires_tools=[], minimum_posture="guarded",
        risk_tier="low", priority=90, max_context_tokens=600, activation_mode="advisory",
        verification_checklist=["Evidence must pass"], body_text="Never expose API_KEY=hidden-value.",
    )


@pytest.mark.asyncio
async def test_activation_creates_candidate_episode_and_trajectory(trajectory_session):
    skill = make_skill()
    trajectory_session.add(skill)
    await trajectory_session.flush()

    result = await SkillActivationService(trajectory_session).activate(SkillActivationRequest(
        run_id="run-trajectory-1", flow_id="flow-1", node_id="node-1", agent_id="shogun",
        model_id="local:test", model_profile="balanced", objective="Capture trajectory evidence",
        posture="campaign", available_tools=["chat"],
    ))

    active = result["active_skills"][0]
    assert active["skill_episode_id"]
    assert active["trajectory_id"]
    assert await trajectory_session.scalar(select(SkillCandidateRetrieval))
    episode = await trajectory_session.scalar(select(SkillEpisode))
    trajectory = await trajectory_session.scalar(select(SkillTrajectory))
    assert episode.flow_id == "flow-1" and episode.node_id == "node-1"
    assert trajectory.trajectory_json["execution_context"]["model_id"] == "local:test"
    assert trajectory.trajectory_json["skill_selection"]["injected"] is True


@pytest.mark.asyncio
async def test_tool_verification_outcome_and_improvement_are_linked(trajectory_session):
    skill = make_skill()
    trajectory_session.add(skill)
    await trajectory_session.flush()
    activated = await SkillActivationService(trajectory_session).activate(SkillActivationRequest(
        run_id="run-failed", objective="trajectory evidence", posture="campaign", available_tools=["chat"],
    ))
    active_id = activated["active_skills"][0]["active_skill_run_id"]
    service = SkillTrajectoryService(trajectory_session)
    await service.link_tool_call(
        [active_id], tool_call_id="call-1", tool_name="workspace.read",
        tool_input={"token": "super-secret"}, tool_output="API_KEY=also-secret\nread failed", status="failed",
    )
    await service.link_verification(
        [active_id], verification_id="verify-1", verification_type="quality_gate",
        expected="Evidence must pass", observed="Evidence failed", status="failed", score=0.1,
    )
    await SkillActivationService(trajectory_session).outcome(active_id, "failed", "Could not satisfy check")
    await trajectory_session.flush()

    trajectory = await trajectory_session.scalar(select(SkillTrajectory))
    assert trajectory.final_outcome == "failure" and trajectory.score < 0
    assert await trajectory_session.scalar(select(SkillToolLink))
    assert await trajectory_session.scalar(select(SkillVerificationLink))
    assert await trajectory_session.scalar(select(SkillImprovementCandidate))
    encoded = json.dumps(trajectory.trajectory_json)
    assert "super-secret" not in encoded and "also-secret" not in encoded


@pytest.mark.asyncio
async def test_redacted_zip_export_and_raw_export_policy(trajectory_session):
    skill = make_skill()
    trajectory_session.add(skill)
    await trajectory_session.flush()
    activated = await SkillActivationService(trajectory_session).activate(SkillActivationRequest(
        run_id="run-export", objective="trajectory token=top-secret", posture="campaign", available_tools=[],
    ))
    await SkillActivationService(trajectory_session).outcome(
        activated["active_skills"][0]["active_skill_run_id"], "success", "password=never-export-this",
    )
    trajectories = list((await trajectory_session.execute(select(SkillTrajectory))).scalars())
    payload, content_type, _ = await SkillTrajectoryExporter(trajectory_session).export(trajectories, "zip")
    assert content_type == "application/zip"
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        exported = archive.read("skill-trajectories.jsonl").decode()
    assert "top-secret" not in exported and "never-export-this" not in exported

    app = FastAPI()
    app.include_router(skills_router, prefix="/api/v1")

    async def override_db():
        yield trajectory_session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        blocked = await client.post("/api/v1/skills/trajectories/export", json={
            "format": "jsonl", "include_raw_prompts": True,
        })
        assert blocked.status_code == 403
        listed = await client.get("/api/v1/skills/trajectories")
        assert listed.status_code == 200 and listed.json()["data"][0]["skill_name"] == skill.name
