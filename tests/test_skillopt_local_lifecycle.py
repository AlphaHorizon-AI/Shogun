"""Local SkillOpt actions must affect actual runtime eligibility and content."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.api import skillopt as api
from shogun.db.base import Base
from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import SkillOptCandidate, SkillVersion
from shogun.schemas.skills import SkillActivationRequest
from shogun.services.active_skill_service import SkillCompatibilityService
from shogun.services.skillopt.versioning import SkillVersionService


@pytest.fixture
async def local_session(monkeypatch):
    from shogun.services import immutable_audit, skill_memory_sync

    monkeypatch.setattr(immutable_audit, "append", lambda **kwargs: None)
    monkeypatch.setattr(skill_memory_sync, "sync_skills_to_all_agent_memories", AsyncMock())
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            yield session
    finally:
        await engine.dispose()


async def _skill_with_version(session, tmp_path):
    skill = Skill(name="Local notes", slug=f"notes-{uuid.uuid4().hex}", status="installed", exam_status="passed")
    session.add(skill)
    await session.flush()
    content_path = tmp_path / f"{skill.id}.md"
    content_path.write_text("Original instructions", encoding="utf-8")
    version = await SkillVersionService(session).create_initial_version(
        skill,
        str(content_path),
        "Original instructions",
    )
    return skill, version


@pytest.mark.asyncio
async def test_approved_validated_candidate_can_be_activated(local_session, tmp_path):
    skill, base = await _skill_with_version(local_session, tmp_path)
    candidate_path = tmp_path / "candidate.md"
    candidate_path.write_text("Revised instructions", encoding="utf-8")
    candidate = SkillOptCandidate(
        training_run_id=uuid.uuid4(),
        skill_id=skill.id,
        base_version_id=base.id,
        candidate_content_path=str(candidate_path),
        candidate_diff_path="unused.diff",
        status="validated",
        static_validation_status="passed",
        validation_score=0.98,
    )
    local_session.add(candidate)
    await local_session.commit()

    await api.approve_local_candidate(candidate.id, db=local_session)
    response = await api.activate_local_candidate(candidate.id, db=local_session)

    assert response["status"] == "activated"
    assert skill.active_version_id != base.id
    active = await local_session.get(SkillVersion, skill.active_version_id)
    assert active.skill_id == skill.id
    assert skill.body_text == "Revised instructions"


@pytest.mark.asyncio
async def test_approval_does_not_replace_validation(local_session, tmp_path):
    skill, base = await _skill_with_version(local_session, tmp_path)
    candidate = SkillOptCandidate(
        training_run_id=uuid.uuid4(),
        skill_id=skill.id,
        base_version_id=base.id,
        candidate_content_path="never-read.md",
        candidate_diff_path="unused.diff",
        status="pending_validation",
        validation_score=None,
    )
    local_session.add(candidate)
    await local_session.commit()

    with pytest.raises(HTTPException) as rejected:
        await api.approve_local_candidate(candidate.id, db=local_session)
    assert rejected.value.status_code == 400
    assert candidate.status == "pending_validation"
    assert skill.active_version_id == base.id


@pytest.mark.asyncio
async def test_quarantine_blocks_new_runtime_activation_and_can_be_cleared(local_session, tmp_path):
    skill, _ = await _skill_with_version(local_session, tmp_path)
    await api.quarantine_local_skill(skill.id, api.QuarantineRequest(reason="Review needed"), db=local_session)
    request = SkillActivationRequest(objective="Summarize local notes", available_tools=[])
    assert SkillCompatibilityService.blocked_reason(skill, request) == "status:quarantined"

    await api.unquarantine_local_skill(skill.id, db=local_session)
    assert skill.status == "installed"
    assert SkillCompatibilityService.blocked_reason(skill, request) != "status:quarantined"


@pytest.mark.asyncio
async def test_rollback_rejects_another_skills_version(local_session, tmp_path):
    skill, original = await _skill_with_version(local_session, tmp_path)
    other_skill, other_version = await _skill_with_version(local_session, tmp_path)

    with pytest.raises(HTTPException) as rejected:
        await api.rollback_local_skill(
            skill.id,
            api.RollbackRequest(target_version_id=other_version.id),
            db=local_session,
        )
    assert rejected.value.status_code == 400
    assert skill.active_version_id == original.id
    assert original.status == "active"
    assert other_skill.active_version_id == other_version.id
    assert other_version.status == "active"


@pytest.mark.asyncio
async def test_unquarantine_does_not_enable_a_skill_that_was_not_quarantined(local_session, tmp_path):
    skill, version = await _skill_with_version(local_session, tmp_path)
    skill.status = "disabled"
    await local_session.commit()

    await SkillVersionService(local_session).unquarantine_version(skill.id)

    assert skill.status == "disabled"
    assert version.status == "active"


@pytest.mark.asyncio
async def test_quarantining_archived_version_preserves_current_skill_and_version_history(local_session, tmp_path):
    skill, original = await _skill_with_version(local_session, tmp_path)
    service = SkillVersionService(local_session)
    archived = await service.create_new_version(
        skill.id,
        original.id,
        original.content_path,
        "Previous instructions",
        status="archived",
    )

    await service.quarantine_version(skill.id, "Review history", version_id=archived.id)
    await service.unquarantine_version(skill.id, version_id=archived.id)

    assert archived.status == "archived"
    assert skill.active_version_id == original.id
    assert skill.status == "installed"


@pytest.mark.asyncio
async def test_rollback_cannot_activate_a_quarantined_version(local_session, tmp_path):
    skill, original = await _skill_with_version(local_session, tmp_path)
    service = SkillVersionService(local_session)
    archived = await service.create_new_version(
        skill.id,
        original.id,
        original.content_path,
        "Previous instructions",
        status="archived",
    )
    await service.quarantine_version(skill.id, "Review history", version_id=archived.id)

    with pytest.raises(HTTPException) as rejected:
        await api.rollback_local_skill(skill.id, api.RollbackRequest(target_version_id=archived.id), db=local_session)

    assert rejected.value.status_code == 400
    assert skill.active_version_id == original.id
    assert archived.status == "quarantined"
