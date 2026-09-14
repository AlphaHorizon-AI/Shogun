"""Governance tests for SkillOpt versioning ownership and immutable native-skill protection.

Verifies:
- Version/skill ownership checks across activation, quarantine, unquarantine, creation, and rollback.
- Rejection of activating a quarantined version.
- Rejection of lifecycle mutations against protected native skills.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from shogun.db.base import Base
from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import SkillVersion
from shogun.services.enterprise_transformation_skill import (
    ENTERPRISE_TRANSFORMATION_SKILL_SLUG,
    ProtectedSkillMutationError,
)
from shogun.services.skill_rollback_service import SkillRollbackService
from shogun.services.skillopt.versioning import SkillVersionService


@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.mark.asyncio
async def test_activate_version_rejects_cross_skill_ownership(async_db: AsyncSession) -> None:
    """activate_version must reject activating a version belonging to a different skill."""
    now = datetime.now(timezone.utc)
    skill_a = Skill(id=uuid.uuid4(), name="Skill A", slug="skill-a")
    skill_b = Skill(id=uuid.uuid4(), name="Skill B", slug="skill-b")

    ver_b = SkillVersion(
        id=uuid.uuid4(),
        skill_id=skill_b.id,
        version_number=1,
        status="candidate",
        content_path="/b/1.md",
        content_hash="hashb",
        created_at=now,
        updated_at=now,
    )
    async_db.add_all([skill_a, skill_b, ver_b])
    await async_db.commit()

    vsvc = SkillVersionService(async_db)
    with pytest.raises(ValueError, match="does not belong to skill"):
        await vsvc.activate_version(skill_a.id, ver_b.id)


@pytest.mark.asyncio
async def test_activate_version_rejects_quarantined_version(async_db: AsyncSession) -> None:
    """activate_version must reject directly activating a version that is currently quarantined."""
    now = datetime.now(timezone.utc)
    skill = Skill(id=uuid.uuid4(), name="Skill A", slug="skill-a")
    ver = SkillVersion(
        id=uuid.uuid4(),
        skill_id=skill.id,
        version_number=2,
        status="quarantined",
        quarantine_status="quarantined",
        content_path="/a/2.md",
        content_hash="hash2",
        created_at=now,
        updated_at=now,
    )
    async_db.add_all([skill, ver])
    await async_db.commit()

    vsvc = SkillVersionService(async_db)
    with pytest.raises(ValueError, match="quarantined"):
        await vsvc.activate_version(skill.id, ver.id)


@pytest.mark.asyncio
async def test_quarantine_version_rejects_cross_skill_ownership(async_db: AsyncSession) -> None:
    """quarantine_version must reject quarantining a version ID that belongs to another skill."""
    now = datetime.now(timezone.utc)
    skill_a = Skill(id=uuid.uuid4(), name="Skill A", slug="skill-a")
    skill_b = Skill(id=uuid.uuid4(), name="Skill B", slug="skill-b")

    ver_b = SkillVersion(
        id=uuid.uuid4(),
        skill_id=skill_b.id,
        version_number=1,
        status="active",
        content_path="/b/1.md",
        content_hash="hashb",
        created_at=now,
        updated_at=now,
    )
    async_db.add_all([skill_a, skill_b, ver_b])
    await async_db.commit()

    vsvc = SkillVersionService(async_db)
    with pytest.raises(ValueError, match="does not belong to skill"):
        await vsvc.quarantine_version(skill_a.id, reason="Policy breach", version_id=ver_b.id)


@pytest.mark.asyncio
async def test_unquarantine_version_rejects_cross_skill_ownership(async_db: AsyncSession) -> None:
    """unquarantine_version must reject unquarantining a version belonging to another skill."""
    now = datetime.now(timezone.utc)
    skill_a = Skill(id=uuid.uuid4(), name="Skill A", slug="skill-a")
    skill_b = Skill(id=uuid.uuid4(), name="Skill B", slug="skill-b")

    ver_b = SkillVersion(
        id=uuid.uuid4(),
        skill_id=skill_b.id,
        version_number=1,
        status="quarantined",
        quarantine_status="quarantined",
        content_path="/b/1.md",
        content_hash="hashb",
        created_at=now,
        updated_at=now,
    )
    async_db.add_all([skill_a, skill_b, ver_b])
    await async_db.commit()

    vsvc = SkillVersionService(async_db)
    with pytest.raises(ValueError, match="does not belong to skill"):
        await vsvc.unquarantine_version(skill_a.id, version_id=ver_b.id)


@pytest.mark.asyncio
async def test_create_new_version_rejects_cross_skill_parent(async_db: AsyncSession) -> None:
    """create_new_version must reject a parent_version_id belonging to another skill."""
    now = datetime.now(timezone.utc)
    skill_a = Skill(id=uuid.uuid4(), name="Skill A", slug="skill-a")
    skill_b = Skill(id=uuid.uuid4(), name="Skill B", slug="skill-b")

    ver_b = SkillVersion(
        id=uuid.uuid4(),
        skill_id=skill_b.id,
        version_number=1,
        status="active",
        content_path="/b/1.md",
        content_hash="hashb",
        created_at=now,
        updated_at=now,
    )
    async_db.add_all([skill_a, skill_b, ver_b])
    await async_db.commit()

    vsvc = SkillVersionService(async_db)
    with pytest.raises(ValueError, match="does not belong to skill"):
        await vsvc.create_new_version(
            skill_id=skill_a.id,
            parent_version_id=ver_b.id,
            content_path="/a/new.md",
            content="New content",
        )


@pytest.mark.asyncio
async def test_rollback_rejects_cross_skill_target(async_db: AsyncSession) -> None:
    """SkillRollbackService must reject rolling back to a target version from another skill."""
    now = datetime.now(timezone.utc)
    skill_a = Skill(id=uuid.uuid4(), name="Skill A", slug="skill-a")
    skill_b = Skill(id=uuid.uuid4(), name="Skill B", slug="skill-b")

    ver_b = SkillVersion(
        id=uuid.uuid4(),
        skill_id=skill_b.id,
        version_number=1,
        status="active",
        content_path="/b/1.md",
        content_hash="hashb",
        created_at=now,
        updated_at=now,
    )
    async_db.add_all([skill_a, skill_b, ver_b])
    await async_db.commit()

    rollback_svc = SkillRollbackService(async_db)
    result = await rollback_svc.rollback(skill_a.id, target_version_id=ver_b.id)
    assert result["status"] == "error"
    assert "does not belong to skill" in result["message"]


# ── Immutable Native-Skill Protection Tests ──────────────────


@pytest.mark.asyncio
async def test_protected_native_skill_rejects_quarantine(async_db: AsyncSession) -> None:
    """Protected native skills cannot be quarantined."""
    now = datetime.now(timezone.utc)
    native_skill = Skill(
        id=uuid.uuid4(),
        name="Enterprise Transformation Architect",
        slug=ENTERPRISE_TRANSFORMATION_SKILL_SLUG,
        is_builtin=True,
        is_protected=True,
    )
    ver = SkillVersion(
        id=uuid.uuid4(),
        skill_id=native_skill.id,
        version_number=1,
        status="active",
        content_path="/native/arch.md",
        content_hash="hasharch",
        created_at=now,
        updated_at=now,
    )
    native_skill.active_version_id = ver.id
    async_db.add_all([native_skill, ver])
    await async_db.commit()

    vsvc = SkillVersionService(async_db)
    with pytest.raises(ProtectedSkillMutationError, match="protected built-in skill"):
        await vsvc.quarantine_version(native_skill.id, reason="Testing protection")


@pytest.mark.asyncio
async def test_protected_native_skill_rejects_unquarantine(async_db: AsyncSession) -> None:
    """Protected native skills cannot be unquarantined."""
    native_skill = Skill(
        id=uuid.uuid4(),
        name="Enterprise Transformation Architect",
        slug=ENTERPRISE_TRANSFORMATION_SKILL_SLUG,
        is_builtin=True,
        is_protected=True,
    )
    async_db.add(native_skill)
    await async_db.commit()

    vsvc = SkillVersionService(async_db)
    with pytest.raises(ProtectedSkillMutationError, match="protected built-in skill"):
        await vsvc.unquarantine_version(native_skill.id)


@pytest.mark.asyncio
async def test_protected_native_skill_rejects_version_activation(async_db: AsyncSession) -> None:
    """Protected native skills cannot have arbitrary versions activated."""
    now = datetime.now(timezone.utc)
    native_skill = Skill(
        id=uuid.uuid4(),
        name="Enterprise Transformation Architect",
        slug=ENTERPRISE_TRANSFORMATION_SKILL_SLUG,
        is_builtin=True,
        is_protected=True,
    )
    ver = SkillVersion(
        id=uuid.uuid4(),
        skill_id=native_skill.id,
        version_number=2,
        status="candidate",
        content_path="/native/v2.md",
        content_hash="hashv2",
        created_at=now,
        updated_at=now,
    )
    async_db.add_all([native_skill, ver])
    await async_db.commit()

    vsvc = SkillVersionService(async_db)
    with pytest.raises(ProtectedSkillMutationError, match="protected built-in skill"):
        await vsvc.activate_version(native_skill.id, ver.id)


@pytest.mark.asyncio
async def test_protected_native_skill_rejects_create_new_version(async_db: AsyncSession) -> None:
    """Protected native skills reject creating candidate versions."""
    native_skill = Skill(
        id=uuid.uuid4(),
        name="Enterprise Transformation Architect",
        slug=ENTERPRISE_TRANSFORMATION_SKILL_SLUG,
        is_builtin=True,
        is_protected=True,
    )
    async_db.add(native_skill)
    await async_db.commit()

    vsvc = SkillVersionService(async_db)
    with pytest.raises(ProtectedSkillMutationError, match="protected built-in skill"):
        await vsvc.create_new_version(
            skill_id=native_skill.id,
            parent_version_id=uuid.uuid4(),
            content_path="/native/new.md",
            content="New kernel",
        )
