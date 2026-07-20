"""Skill Lifecycle API — Order 15.

Endpoints for the full OpenClaw College Content Loop:
validation, quality gate, packaging, publishing, rollback, metrics, authoring.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db

router = APIRouter(prefix="/skills/lifecycle", tags=["Skill Lifecycle"])


# ── Request/Response Models ──────────────────────────────────

class AuthorSkillRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    category: str = "general"
    description: str = ""
    body_text: str = ""
    triggers: list[str] = Field(default_factory=list)
    use_when: list[str] = Field(default_factory=list)
    avoid_when: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    workflow_steps: list[str] = Field(default_factory=list)
    decision_rules: list[str] = Field(default_factory=list)
    output_requirements: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    failure_handling: list[str] = Field(default_factory=list)
    example_input: str = ""
    example_output: str = ""
    risk_tier: str = "low"
    requires_tools: list[str] = Field(default_factory=list)
    optional_tools: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    version: str = "1.0.0"
    author: str = "operator"


class AddTestRequest(BaseModel):
    test_type: str = "output_quality"
    test_definition: dict[str, Any] = Field(default_factory=dict)


class PublishRequest(BaseModel):
    provider: str = "local"
    skip_quality_gate: bool = False


class RollbackRequest(BaseModel):
    target_version_id: uuid.UUID | None = None


class RecordUsageRequest(BaseModel):
    version: str
    outcome: str  # "success" | "failure"
    score: float | None = None


# ── Author ───────────────────────────────────────────────────

@router.post("/author", status_code=201)
async def author_skill(body: AuthorSkillRequest, db: AsyncSession = Depends(get_db)):
    """Create a new skill draft via the authoring workflow."""
    from shogun.services.skill_authoring_service import SkillAuthoringService
    svc = SkillAuthoringService(db)
    try:
        result = await svc.create_skill_draft(
            name=body.name,
            category=body.category,
            description=body.description,
            body_text=body.body_text,
            triggers=body.triggers,
            use_when=body.use_when,
            avoid_when=body.avoid_when,
            required_inputs=body.required_inputs,
            workflow_steps=body.workflow_steps,
            decision_rules=body.decision_rules,
            output_requirements=body.output_requirements,
            success_criteria=body.success_criteria,
            failure_handling=body.failure_handling,
            example_input=body.example_input,
            example_output=body.example_output,
            risk_tier=body.risk_tier,
            requires_tools=body.requires_tools,
            optional_tools=body.optional_tools,
            tags=body.tags,
            version=body.version,
            author=body.author,
        )
        await db.commit()
        return {"status": "success", "data": result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# ── Tests ────────────────────────────────────────────────────

@router.post("/{skill_id}/tests", status_code=201)
async def add_tests(
    skill_id: uuid.UUID,
    body: list[AddTestRequest] | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Add validation tests to a skill. Pass empty body to auto-generate."""
    from shogun.services.skill_authoring_service import SkillAuthoringService
    svc = SkillAuthoringService(db)
    test_defs = [
        {"test_type": t.test_type, **t.test_definition} for t in body
    ] if body else None
    try:
        result = await svc.generate_validation_tests(skill_id, tests=test_defs)
        await db.commit()
        return {"status": "success", "tests": result}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{skill_id}/tests")
async def list_tests(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List validation tests for a skill."""
    from sqlalchemy import select

    from shogun.db.models.skill_test import SkillTest
    result = await db.execute(
        select(SkillTest).where(SkillTest.skill_id == skill_id)
    )
    tests = result.scalars().all()
    return {
        "status": "success",
        "tests": [
            {
                "id": str(t.id),
                "test_type": t.test_type,
                "version": t.version,
                "definition": t.test_definition_json,
                "last_result": t.last_result_json,
                "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
            }
            for t in tests
        ],
    }


# ── Quality Gate ─────────────────────────────────────────────

@router.post("/{skill_id}/quality-gate")
async def run_quality_gate(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Run the quality gate on a skill."""
    from shogun.services.skill_quality_gate import SkillQualityGateService
    svc = SkillQualityGateService(db)
    result = await svc.run_quality_gate(skill_id)
    await db.commit()
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])
    return result


@router.get("/{skill_id}/validation-results")
async def get_validation_results(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get validation/quality gate history for a skill."""
    from sqlalchemy import select

    from shogun.db.models.skill_test import SkillTest
    result = await db.execute(
        select(SkillTest).where(SkillTest.skill_id == skill_id).order_by(SkillTest.last_run_at.desc())
    )
    tests = result.scalars().all()
    return {
        "status": "success",
        "results": [
            {
                "id": str(t.id),
                "test_type": t.test_type,
                "version": t.version,
                "result": t.last_result_json,
                "run_at": t.last_run_at.isoformat() if t.last_run_at else None,
            }
            for t in tests
        ],
    }


# ── Validate ─────────────────────────────────────────────────

@router.post("/{skill_id}/validate")
async def validate_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Run quality gate and transition to 'validated' if passed."""
    from shogun.db.models.skill import Skill
    from shogun.services.skill_quality_gate import SkillQualityGateService
    svc = SkillQualityGateService(db)
    result = await svc.run_quality_gate(skill_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result["message"])

    if result["status"] == "passed":
        skill = await db.get(Skill, skill_id)
        if skill and skill.lifecycle_state in ("draft", "optimized"):
            skill.lifecycle_state = "validated"
            await db.flush()
        result["lifecycle_state"] = "validated"
    await db.commit()
    return result


# ── Package ──────────────────────────────────────────────────

@router.post("/{skill_id}/package")
async def package_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Package a skill for publishing."""
    from shogun.services.skill_publishing import SkillPublishingService
    svc = SkillPublishingService(db)
    try:
        package_path = await svc.package_skill(skill_id)
        return {"status": "success", "package_path": str(package_path)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# ── Publish ──────────────────────────────────────────────────

@router.post("/{skill_id}/publish")
async def publish_skill(
    skill_id: uuid.UUID,
    body: PublishRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Publish a skill to a provider."""
    from shogun.services.skill_publishing import SkillPublishingService
    provider = (body.provider if body else "local")
    skip_gate = (body.skip_quality_gate if body else False)
    svc = SkillPublishingService(db)
    result = await svc.publish(skill_id, provider_name=provider, skip_quality_gate=skip_gate)
    await db.commit()
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/{skill_id}/republish")
async def republish_skill(
    skill_id: uuid.UUID,
    body: PublishRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Republish an optimized/revalidated skill."""
    from shogun.services.skill_publishing import SkillPublishingService
    provider = (body.provider if body else "local")
    svc = SkillPublishingService(db)
    result = await svc.republish(skill_id, provider_name=provider)
    await db.commit()
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/{skill_id}/publication-status")
async def get_publication_status(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get publication history for a skill."""
    from sqlalchemy import select

    from shogun.db.models.skill_publication import SkillPublication
    result = await db.execute(
        select(SkillPublication).where(SkillPublication.skill_id == skill_id)
        .order_by(SkillPublication.created_at.desc())
    )
    pubs = result.scalars().all()
    return {
        "status": "success",
        "publications": [
            {
                "id": str(p.id),
                "version": p.version,
                "provider": p.provider,
                "published_url": p.published_url,
                "publication_status": p.publication_status,
                "published_at": p.published_at.isoformat() if p.published_at else None,
            }
            for p in pubs
        ],
    }


# ── Rollback ─────────────────────────────────────────────────

@router.post("/{skill_id}/rollback")
async def rollback_skill(
    skill_id: uuid.UUID,
    body: RollbackRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Rollback a skill to a previous version."""
    from shogun.services.skill_rollback_service import SkillRollbackService
    target = body.target_version_id if body else None
    svc = SkillRollbackService(db)
    result = await svc.rollback(skill_id, target_version_id=target)
    await db.commit()
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.get("/{skill_id}/versions")
async def get_versions(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """List all versions for a skill."""
    from shogun.services.skill_rollback_service import SkillRollbackService
    svc = SkillRollbackService(db)
    versions = await svc.get_versions(skill_id)
    return {"status": "success", "versions": versions}


# ── Deprecate / Archive ──────────────────────────────────────

@router.post("/{skill_id}/deprecate")
async def deprecate_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Mark a skill as deprecated."""
    from shogun.services.skill_rollback_service import SkillRollbackService
    svc = SkillRollbackService(db)
    result = await svc.deprecate(skill_id)
    await db.commit()
    return result


@router.post("/{skill_id}/archive")
async def archive_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Archive a skill (remove from active use, retain for history)."""
    from shogun.services.skill_rollback_service import SkillRollbackService
    svc = SkillRollbackService(db)
    result = await svc.archive(skill_id)
    await db.commit()
    return result


# ── Metrics ──────────────────────────────────────────────────

@router.get("/{skill_id}/metrics")
async def get_skill_metrics(
    skill_id: uuid.UUID,
    version: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get performance metrics for a skill."""
    from shogun.services.skill_metrics_service import SkillMetricsService
    svc = SkillMetricsService(db)
    metrics = await svc.get_metrics(skill_id, version=version)
    return {"status": "success", "metrics": metrics}


@router.post("/{skill_id}/record-usage")
async def record_usage(
    skill_id: uuid.UUID,
    body: RecordUsageRequest,
    db: AsyncSession = Depends(get_db),
):
    """Record a usage event and update skill metrics."""
    from shogun.services.skill_metrics_service import SkillMetricsService
    svc = SkillMetricsService(db)
    metrics = await svc.record_usage(skill_id, body.version, body.outcome, body.score)
    await db.commit()
    return {"status": "success", "metrics": SkillMetricsService._to_dict(metrics)}


@router.get("/underperforming")
async def get_underperforming(
    threshold: float = 0.7,
    db: AsyncSession = Depends(get_db),
):
    """Get skills performing below a threshold."""
    from shogun.services.skill_metrics_service import SkillMetricsService
    svc = SkillMetricsService(db)
    results = await svc.get_underperforming(threshold)
    return {"status": "success", "skills": results}
