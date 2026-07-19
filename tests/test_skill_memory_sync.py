from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
import shogun.engine.vector_store as vector_store_module
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.skill import Skill
from shogun.db.models.skill_installation import SkillInstallation
from shogun.db.models.skillopt import SkillOptCandidate, SkillOptTrainingRun, SkillVersion
from shogun.services.skill_memory_sync import (
    mark_skill_achieved_and_sync,
    sync_skills_to_memory,
)
from shogun.services.skillopt.promotion import SkillPromotionService


class FakeVectorStore:
    def __init__(self) -> None:
        self.points: dict[str, dict] = {}

    def upsert(self, memory_id: str, text: str, payload: dict) -> None:
        self.points[memory_id] = {"text": text, "payload": payload}


@pytest.fixture
async def skill_sync_context(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    vector_store = FakeVectorStore()
    monkeypatch.setattr(vector_store_module, "get_vector_store", lambda: vector_store)

    async with sessions() as session:
        yield session, vector_store

    await engine.dispose()


@pytest.mark.asyncio
async def test_sync_migrates_legacy_records_and_includes_every_installed_skill(skill_sync_context):
    session, vector_store = skill_sync_context
    agent_id = uuid.uuid4()
    direct_skill = Skill(
        name="Direct Skill",
        slug="direct-skill",
        version="1.0.0",
        status="installed",
        manifest={"description": "Installed directly from Dojo."},
    )
    installation_skill = Skill(
        name="Installation Skill",
        slug="installation-skill",
        version="1.0.0",
        status="available",
        manifest={},
    )
    achieved_skill = Skill(
        name="Achieved Skill",
        slug="achieved-skill",
        version="1.0.0",
        status="available",
        exam_status="passed",
        body_text="A full achieved-skill workflow with task-specific validation.",
        manifest={"description": "Passed previously."},
    )
    session.add_all([direct_skill, installation_skill, achieved_skill])
    await session.flush()
    session.add_all(
        [
            SkillInstallation(
                skill_id=direct_skill.id,
                openclaw_skill_id="college-direct",
                installed_version="1.0.0",
                installed_at=datetime.now(timezone.utc),
            ),
            SkillInstallation(
                skill_id=installation_skill.id,
                openclaw_skill_id="college-installation",
                installed_version="1.0.0",
                installed_at=datetime.now(timezone.utc),
            ),
        ]
    )
    legacy_record = MemoryRecord(
        agent_id=agent_id,
        memory_type="skill",
        title="Old direct skill",
        content="Old content",
        tags=["skill:direct-skill"],
    )
    removed_record = MemoryRecord(
        agent_id=agent_id,
        memory_type="skills",
        title="Removed skill",
        content="No longer installed",
        tags=["skill:removed-skill"],
    )
    session.add_all([legacy_record, removed_record])
    await session.commit()

    stats = await sync_skills_to_memory(session, agent_id)

    records = list(
        (
            await session.execute(
                select(MemoryRecord).where(MemoryRecord.agent_id == agent_id)
            )
        ).scalars()
    )
    active = [record for record in records if not record.is_archived]
    assert stats == {"added": 2, "updated": 1, "archived": 1, "errors": 0, "total": 3}
    assert len(active) == 3
    assert {record.memory_type for record in active} == {"skills"}
    assert {record.title for record in active} == {
        "Skill: Direct Skill",
        "Skill: Installation Skill",
        "Skill: Achieved Skill",
    }
    assert legacy_record.id in {record.id for record in active}
    assert next(record for record in active if record.title.endswith("Installation Skill")).content == (
        "Installation Skill"
    )
    assert removed_record.is_archived is True
    assert len(vector_store.points) == 3
    assert {point["payload"]["memory_type"] for point in vector_store.points.values()} == {"skills"}
    assert {point["payload"]["skill_id"] for point in vector_store.points.values()} == {
        str(direct_skill.id), str(installation_skill.id), str(achieved_skill.id),
    }
    achieved_point = next(
        point for point in vector_store.points.values()
        if point["payload"]["skill_id"] == str(achieved_skill.id)
    )
    assert "full achieved-skill workflow" in achieved_point["text"]

    assert await mark_skill_achieved_and_sync(session, agent_id, "college-direct") is True
    assert direct_skill.exam_status == "passed"
    assert "exam:passed" in legacy_record.tags

    repeat = await sync_skills_to_memory(session, agent_id)
    assert repeat == {"added": 0, "updated": 0, "archived": 0, "errors": 0, "total": 3}


@pytest.mark.asyncio
async def test_skillopt_promotion_replaces_the_canonical_archive_markdown(skill_sync_context, tmp_path):
    session, _ = skill_sync_context
    agent = Agent(agent_type="shogun", name="Primary", slug="primary", status="active", is_primary=True)
    skill = Skill(
        name="Optimizable Skill",
        slug="optimizable-skill",
        version="1.0.0",
        status="installed",
        body_text="# Original\n\nOriginal procedure.",
        manifest={"canonical_content_source": "openclaw_college"},
    )
    session.add_all([agent, skill])
    await session.flush()

    original_path = tmp_path / "original.md"
    original_path.write_text(skill.body_text, encoding="utf-8")
    version = SkillVersion(
        skill_id=skill.id,
        version_number=1,
        status="active",
        content_path=str(original_path),
        content_hash="original",
        created_by="openclaw_college",
    )
    session.add(version)
    await session.flush()
    skill.active_version_id = version.id

    run = SkillOptTrainingRun(
        skill_id=skill.id,
        base_version_id=version.id,
        status="completed",
    )
    session.add(run)
    await session.flush()
    optimized_markdown = "# Optimized\n\nUse the improved golden procedure."
    candidate_path = tmp_path / "candidate.md"
    candidate_path.write_text(optimized_markdown, encoding="utf-8")
    diff_path = tmp_path / "candidate.diff"
    diff_path.write_text("optimized", encoding="utf-8")
    candidate = SkillOptCandidate(
        training_run_id=run.id,
        skill_id=skill.id,
        base_version_id=version.id,
        candidate_content_path=str(candidate_path),
        candidate_diff_path=str(diff_path),
        status="validated",
        validation_score=0.9,
    )
    session.add(candidate)
    await session.commit()

    assert await SkillPromotionService(session).promote_candidate(candidate.id) is True

    record = (
        await session.execute(
            select(MemoryRecord).where(
                MemoryRecord.agent_id == agent.id,
                MemoryRecord.source_ref_id == skill.id,
                MemoryRecord.is_archived.is_(False),
            )
        )
    ).scalar_one()
    assert skill.body_text == optimized_markdown
    assert skill.manifest["optimized_by"] == "skillopt"
    assert record.content == optimized_markdown
    assert candidate.status == "promoted"
