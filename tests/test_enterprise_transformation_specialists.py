from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import shogun.db.models  # noqa: F401
from shogun.db.base import Base
from shogun.services.enterprise_transformation_skill import is_protected_builtin_skill
from shogun.services.enterprise_transformation_specialists import (
    ENTERPRISE_TRANSFORMATION_SPECIALIST_SLUGS,
    SPECIALIST_SPECS,
    ensure_enterprise_transformation_specialist_skills,
)


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
async def test_bootstrap_creates_every_protected_platform_specialist(skill_session):
    skills = await ensure_enterprise_transformation_specialist_skills(skill_session)

    assert {skill.slug for skill in skills} == ENTERPRISE_TRANSFORMATION_SPECIALIST_SLUGS
    assert len(skills) == len(SPECIALIST_SPECS) == 12
    assert all(skill.is_builtin and skill.is_protected for skill in skills)
    assert all(is_protected_builtin_skill(skill) for skill in skills)
    assert all(skill.activation_mode == "advisory" for skill in skills)
    assert all("transformation_sources_inspect" in skill.requires_tools for skill in skills)
    assert all(skill.conflict_group == "enterprise-transformation-platform-specialist" for skill in skills)


@pytest.mark.asyncio
async def test_bootstrap_repairs_specialist_without_changing_identity(skill_session):
    skills = await ensure_enterprise_transformation_specialist_skills(skill_session)
    sap = next(skill for skill in skills if skill.slug == "sap-transformation-specialist")
    original_id = sap.id
    sap.name = "Tampered"
    sap.is_builtin = False
    sap.is_protected = False
    sap.body_text = "customer-specific private rules"
    await skill_session.flush()

    repaired = await ensure_enterprise_transformation_specialist_skills(skill_session)
    sap = next(skill for skill in repaired if skill.slug == "sap-transformation-specialist")

    assert sap.id == original_id
    assert sap.name == "SAP Transformation Specialist"
    assert sap.is_builtin is True
    assert sap.is_protected is True
    assert "customer-specific private rules" not in sap.body_text
    assert "tenant" in sap.body_text.lower()


def test_specialist_prefixes_cover_every_public_profile_family():
    prefixes = {prefix for spec in SPECIALIST_SPECS for prefix in spec.profile_prefixes}
    expected = {
        "d365_fscm_",
        "business_central_",
        "salesforce_",
        "oracle_fusion_",
        "netsuite_",
        "ifs_cloud_",
        "epicor_kinetic_",
        "servicenow_",
        "hubspot_",
        "quickbooks_online_",
        "xero_",
        "economic_",
        "sage_intacct_",
        "workday_",
    }
    assert expected <= prefixes

    resource_root = (
        Path(__file__).resolve().parents[1]
        / "shogun"
        / "resources"
        / "transformation_profiles"
    )
    uncovered: list[str] = []
    for path in resource_root.glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("resource_type") != "transformation_profile":
            continue
        profile_id = str(payload.get("id") or "")
        if not any(profile_id.startswith(prefix) for prefix in prefixes):
            uncovered.append(profile_id)
    assert uncovered == []
