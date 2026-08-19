from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import shogun.db.models  # noqa: F401
from shogun.db.base import Base
from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import SkillOptCandidate
from shogun.services.enterprise_transformation_skill import (
    ENTERPRISE_TRANSFORMATION_SKILL_PATH,
    ENTERPRISE_TRANSFORMATION_SKILL_SLUG,
    ProtectedSkillMutationError,
    ensure_enterprise_transformation_skill,
)
from shogun.services.skill_rollback_service import SkillRollbackService
from shogun.services.skill_service import SkillService
from shogun.services.skillopt.promotion import SkillPromotionService


@pytest_asyncio.fixture
async def skill_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_bootstrap_creates_protected_enterprise_transformation_skill(skill_session):
    skill = await ensure_enterprise_transformation_skill(skill_session)

    assert skill.slug == ENTERPRISE_TRANSFORMATION_SKILL_SLUG
    assert skill.is_builtin is True
    assert skill.is_protected is True
    assert skill.status == "installed"
    assert skill.lifecycle_state == "active"
    assert skill.is_deleted is False
    assert skill.local_path == str(ENTERPRISE_TRANSFORMATION_SKILL_PATH)
    assert "SkillOpt evolves the transformation-profile registry" in skill.body_text
    assert "document text" in skill.brief_text


@pytest.mark.asyncio
async def test_bootstrap_repairs_damage_without_replacing_identity(skill_session):
    skill = await ensure_enterprise_transformation_skill(skill_session)
    original_id = skill.id
    skill.name = "Tampered"
    skill.is_builtin = False
    skill.is_protected = False
    skill.status = "archived"
    skill.lifecycle_state = "archived"
    skill.is_deleted = True
    skill.deleted_at = skill.created_at
    skill.body_text = "tampered body"
    await skill_session.flush()

    repaired = await ensure_enterprise_transformation_skill(skill_session)

    assert repaired.id == original_id
    assert repaired.name == "Enterprise Transformation Architect"
    assert repaired.is_builtin is True
    assert repaired.is_protected is True
    assert repaired.status == "installed"
    assert repaired.lifecycle_state == "active"
    assert repaired.is_deleted is False
    assert repaired.deleted_at is None
    assert "tampered body" not in repaired.body_text


@pytest.mark.asyncio
async def test_bootstrap_recovers_physically_missing_skill(skill_session):
    original = await ensure_enterprise_transformation_skill(skill_session)
    original_id = original.id
    await skill_session.delete(original)
    await skill_session.flush()

    recovered = await ensure_enterprise_transformation_skill(skill_session)

    assert recovered.id != original_id
    assert recovered.is_builtin is True
    assert recovered.is_protected is True
    records = (
        await skill_session.execute(
            select(Skill).where(Skill.slug == ENTERPRISE_TRANSFORMATION_SKILL_SLUG)
        )
    ).scalars().all()
    assert records == [recovered]


@pytest.mark.asyncio
async def test_generic_delete_rejects_protected_skill_even_if_flags_are_cleared(skill_session):
    skill = await ensure_enterprise_transformation_skill(skill_session)
    skill.is_builtin = False
    skill.is_protected = False
    await skill_session.flush()

    with pytest.raises(ProtectedSkillMutationError, match="Cannot delete protected built-in skill"):
        await SkillService(skill_session).delete(skill.id)

    assert skill.is_deleted is False


@pytest.mark.asyncio
async def test_generic_update_and_skillopt_promotion_reject_protected_kernel(skill_session):
    skill = await ensure_enterprise_transformation_skill(skill_session)

    with pytest.raises(ProtectedSkillMutationError, match="Cannot update protected built-in skill"):
        await SkillService(skill_session).update(skill.id, body_text="replace the kernel")

    candidate = SkillOptCandidate(
        training_run_id=uuid.uuid4(),
        skill_id=skill.id,
        base_version_id=uuid.uuid4(),
        candidate_content_path="unused-because-protection-runs-first.md",
        candidate_diff_path="unused.diff",
        status="validated",
        validation_score=1.0,
    )
    skill_session.add(candidate)
    await skill_session.flush()

    with pytest.raises(ProtectedSkillMutationError, match="promote a SkillOpt candidate"):
        await SkillPromotionService(skill_session).promote_candidate(candidate.id)

    assert "SkillOpt evolves the transformation-profile registry" in skill.body_text


@pytest.mark.asyncio
async def test_archive_and_deprecate_reject_protected_skill(skill_session):
    skill = await ensure_enterprise_transformation_skill(skill_session)
    service = SkillRollbackService(skill_session)

    deprecated = await service.deprecate(skill.id)
    archived = await service.archive(skill.id)
    rolled_back = await service.rollback(skill.id)

    assert deprecated["code"] == "protected_builtin_skill"
    assert archived["code"] == "protected_builtin_skill"
    assert rolled_back["code"] == "protected_builtin_skill"
    assert skill.lifecycle_state == "active"
    assert skill.status == "installed"
    assert skill.archived_at is None


@pytest.mark.asyncio
async def test_lifecycle_operations_still_work_for_mutable_skills(skill_session):
    mutable = Skill(
        id=uuid.uuid4(),
        name="Mutable Skill",
        slug="mutable-skill",
        version="1.0.0",
        status="installed",
    )
    archived = Skill(
        id=uuid.uuid4(),
        name="Archivable Skill",
        slug="archivable-skill",
        version="1.0.0",
        status="installed",
    )
    deleted = Skill(
        id=uuid.uuid4(),
        name="Deletable Skill",
        slug="deletable-skill",
        version="1.0.0",
        status="installed",
    )
    skill_session.add_all([mutable, archived, deleted])
    await skill_session.flush()

    deprecated_result = await SkillRollbackService(skill_session).deprecate(mutable.id)
    archived_result = await SkillRollbackService(skill_session).archive(archived.id)
    deleted_result = await SkillService(skill_session).delete(deleted.id)

    assert deprecated_result["status"] == "success"
    assert mutable.lifecycle_state == "deprecated"
    assert archived_result["status"] == "success"
    assert archived.lifecycle_state == "archived"
    assert deleted_result is True
    assert deleted.is_deleted is True
