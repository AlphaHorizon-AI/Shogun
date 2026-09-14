"""SkillOpt API router — Yellow Label SkillOpt Lab surface.

Provides the full Yellow Label API from build paper §25:
- Lab optimization runs
- Local skill versions, approval, rollback, quarantine
- Regression suites
- Model benchmarks
"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.services.capability_service import CapabilityService, CapabilityUnavailable

router = APIRouter(prefix="/skillopt", tags=["skillopt"])


# ── Request Models ───────────────────────────────────────────


class TrainingRunRequest(BaseModel):
    skill_id: uuid.UUID
    optimizer_model: str = "high_capability"
    target_model_profile: str = "balanced"


class CandidatePromotionRequest(BaseModel):
    candidate_id: uuid.UUID


class CandidateRejectionRequest(BaseModel):
    candidate_id: uuid.UUID
    reason: str


class LabRunRequest(BaseModel):
    skill_id: uuid.UUID
    optimizer_model: str = "high_capability"
    execution_mode: str = "mock"
    max_iterations: int = 10
    max_llm_calls: int = 40
    max_tool_calls: int = 100
    max_runtime_seconds: int = 900
    max_cost_eur: float = 5.0
    config: dict[str, Any] = Field(default_factory=dict)


class RegressionSuiteRequest(BaseModel):
    skill_id: uuid.UUID
    name: str
    description: str | None = None
    minimum_pass_rate: float = 0.95


class RegressionCaseRequest(BaseModel):
    case_id: str
    name: str
    description: str | None = None
    input_json: dict[str, Any] = Field(default_factory=dict)
    expected_output_json: dict[str, Any] = Field(default_factory=dict)
    evaluation_criteria_json: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class BenchmarkRequest(BaseModel):
    skill_id: uuid.UUID
    model_ids: list[str]
    regression_suite_id: uuid.UUID
    skill_version_id: uuid.UUID | None = None


class QuarantineRequest(BaseModel):
    reason: str


class RollbackRequest(BaseModel):
    target_version_id: uuid.UUID | None = None


# ── Capability guard ─────────────────────────────────────────


def _guard(capability: str) -> None:
    """Raise HTTPException if capability is unavailable."""
    try:
        CapabilityService.get().require(capability)
    except CapabilityUnavailable as exc:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "CAPABILITY_UNAVAILABLE",
                "capability": exc.capability,
                "edition": exc.edition,
            },
        )


# ══════════════════════════════════════════════════════════════
# EXISTING ENDPOINTS (preserved)
# ══════════════════════════════════════════════════════════════


@router.post("/runs")
async def start_training_run(request: TrainingRunRequest, db: AsyncSession = Depends(get_db)):
    """Start a new SkillOpt training run."""
    from shogun.services.skillopt.optimizer import SkillOptService

    svc = SkillOptService(db)
    try:
        run = await svc.start_training_run(
            skill_id=request.skill_id,
            optimizer_model=request.optimizer_model,
            target_model_profile=request.target_model_profile,
        )
        return {"id": run.id, "status": run.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/skills/{skill_id}/versions")
async def get_skill_versions(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get all versions for a skill."""
    from shogun.services.skillopt.versioning import SkillVersionService

    svc = SkillVersionService(db)
    versions = await svc.get_versions(skill_id)
    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "status": v.status,
            "created_at": v.created_at,
            "validation_score": v.validation_score,
            "scope": getattr(v, "scope", "local"),
            "quarantine_status": getattr(v, "quarantine_status", None),
        }
        for v in versions
    ]


@router.post("/candidates/{candidate_id}/promote")
async def promote_candidate(candidate_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Promote a candidate to active version."""
    from shogun.services.skillopt.promotion import SkillPromotionService

    svc = SkillPromotionService(db)
    try:
        success = await svc.promote_candidate(candidate_id)
        if not success:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return {"status": "promoted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/candidates/{candidate_id}/reject")
async def reject_candidate(request: CandidateRejectionRequest, db: AsyncSession = Depends(get_db)):
    """Reject a candidate."""
    from shogun.services.skillopt.promotion import SkillPromotionService

    svc = SkillPromotionService(db)
    success = await svc.reject_candidate(request.candidate_id, request.reason)
    if not success:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"status": "rejected"}


@router.get("/skills/{skill_id}/usage")
async def get_skill_usage(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get usage events for a skill."""
    from shogun.services.skillopt.usage_tracking import SkillUsageTrackingService

    svc = SkillUsageTrackingService(db)
    events = await svc.get_usage_for_skill(skill_id)
    return [
        {
            "id": e.id,
            "skill_version_id": e.skill_version_id,
            "outcome": e.outcome,
            "score": e.score,
            "created_at": e.created_at,
        }
        for e in events
    ]


# ══════════════════════════════════════════════════════════════
# LAB ENDPOINTS (§25 — Lab)
# ══════════════════════════════════════════════════════════════


@router.post("/lab/runs")
async def create_lab_run(request: LabRunRequest, db: AsyncSession = Depends(get_db)):
    """Start a new SkillOpt Lab optimization run."""
    _guard("skillopt.lab")
    from shogun.services.skillopt.lab import SkillOptLabService

    svc = SkillOptLabService(db)
    try:
        run = await svc.create_lab_run(
            skill_id=request.skill_id,
            optimizer_model=request.optimizer_model,
            execution_mode=request.execution_mode,
            max_iterations=request.max_iterations,
            max_llm_calls=request.max_llm_calls,
            max_tool_calls=request.max_tool_calls,
            max_runtime_seconds=request.max_runtime_seconds,
            max_cost_eur=request.max_cost_eur,
            config=request.config,
        )
        return {
            "id": str(run.id),
            "status": run.status,
            "message": "Lab run created. Automated optimizer execution is unavailable in this release.",
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/lab/runs/{run_id}/execute")
async def execute_lab_run_endpoint(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Execute a Lab run."""
    _guard("skillopt.lab")
    from shogun.services.skillopt.lab import SkillOptLabService

    svc = SkillOptLabService(db)
    try:
        run = await svc.execute_lab_run(run_id)
        return {
            "id": str(run.id),
            "status": run.status,
            "message": "SkillOpt Lab proactive optimization execution is unavailable in this release.",
            "result": run.result_json,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/lab/runs")
async def list_lab_runs(
    skill_id: uuid.UUID | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List SkillOpt Lab runs."""
    _guard("skillopt.lab")
    from shogun.services.skillopt.lab import SkillOptLabService

    svc = SkillOptLabService(db)
    runs = await svc.list_runs(skill_id=skill_id, status=status)
    return [
        {
            "id": str(r.id),
            "skill_id": str(r.skill_id),
            "status": r.status,
            "current_iteration": r.current_iteration,
            "max_iterations": r.max_iterations,
            "best_score": r.best_score,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]


@router.get("/lab/runs/{run_id}")
async def get_lab_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single Lab run by ID."""
    _guard("skillopt.lab")
    from shogun.services.skillopt.lab import SkillOptLabService

    svc = SkillOptLabService(db)
    run = await svc.get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Lab run not found")
    return {
        "id": str(run.id),
        "skill_id": str(run.skill_id),
        "status": run.status,
        "optimizer_model": run.optimizer_model,
        "execution_mode": run.execution_mode,
        "current_iteration": run.current_iteration,
        "max_iterations": run.max_iterations,
        "total_llm_calls": run.total_llm_calls,
        "total_tool_calls": run.total_tool_calls,
        "total_cost_eur": run.total_cost_eur,
        "best_score": run.best_score,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "result": run.result_json,
        "config": run.config_json,
    }


@router.post("/lab/runs/{run_id}/cancel")
async def cancel_lab_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Cancel a running Lab optimization run."""
    _guard("skillopt.lab")
    from shogun.services.skillopt.lab import SkillOptLabService

    svc = SkillOptLabService(db)
    try:
        run = await svc.cancel_lab_run(run_id)
        return {"id": str(run.id), "status": run.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════════
# LOCAL SKILLS ENDPOINTS (§25 — Local Skills)
# ══════════════════════════════════════════════════════════════


@router.get("/local/skills")
async def list_local_skills(db: AsyncSession = Depends(get_db)):
    """List all local skills with versioning info."""
    from sqlalchemy import select

    from shogun.db.models.skill import Skill

    stmt = select(Skill).where(Skill.is_deleted.is_(False)).order_by(Skill.name)
    result = await db.execute(stmt)
    skills = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "name": s.name,
            "slug": s.slug,
            "status": s.status,
            "lifecycle_state": s.lifecycle_state,
            "active_version_id": str(s.active_version_id) if s.active_version_id else None,
            "version": s.version,
            "is_builtin": s.is_builtin,
        }
        for s in skills
    ]


@router.get("/local/skills/{skill_id}")
async def get_local_skill(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get detailed info about a local skill."""
    from shogun.db.models.skill import Skill
    from shogun.services.skillopt.versioning import SkillVersionService

    skill = await db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")

    vsvc = SkillVersionService(db)
    versions = await vsvc.get_versions(skill_id)
    active = await vsvc.get_active_version(skill_id)

    return {
        "id": str(skill.id),
        "name": skill.name,
        "slug": skill.slug,
        "status": skill.status,
        "lifecycle_state": skill.lifecycle_state,
        "active_version": {
            "id": str(active.id),
            "version_number": active.version_number,
            "status": active.status,
            "quarantine_status": getattr(active, "quarantine_status", None),
            "validation_score": active.validation_score,
        }
        if active
        else None,
        "version_count": len(versions),
        "is_builtin": skill.is_builtin,
        "risk_tier": skill.risk_tier,
    }


@router.get("/local/skills/{skill_id}/versions")
async def get_local_skill_versions(skill_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get all versions of a local skill."""
    from shogun.services.skillopt.versioning import SkillVersionService

    svc = SkillVersionService(db)
    versions = await svc.get_versions(skill_id)
    return [
        {
            "id": str(v.id),
            "version_number": v.version_number,
            "status": v.status,
            "content_hash": v.content_hash,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "created_by": v.created_by,
            "validation_score": v.validation_score,
            "scope": getattr(v, "scope", "local"),
            "quarantine_status": getattr(v, "quarantine_status", None),
            "activated_at": getattr(v, "activated_at", None),
        }
        for v in versions
    ]


@router.post("/local/candidates/{candidate_id}/approve")
async def approve_local_candidate(candidate_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Approve a candidate for local activation."""
    _guard("skillopt.local_versions")
    from shogun.db.models.skillopt import SkillOptCandidate

    candidate = await db.get(SkillOptCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    if candidate.status != "validated" or not candidate.validation_score:
        raise HTTPException(
            status_code=400,
            detail="Candidate must be successfully validated with a validation score before approval",
        )

    candidate.status = "approved"
    await db.commit()
    return {"status": "approved", "candidate_id": str(candidate_id)}


@router.post("/local/candidates/{candidate_id}/activate")
async def activate_local_candidate(candidate_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Activate an approved candidate as the active skill version."""
    _guard("skillopt.local_versions")
    from shogun.services.skillopt.promotion import SkillPromotionService

    svc = SkillPromotionService(db)
    try:
        success = await svc.promote_candidate(candidate_id, created_by="local-admin")
        if not success:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return {"status": "activated"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/local/skills/{skill_id}/rollback")
async def rollback_local_skill(
    skill_id: uuid.UUID,
    request: RollbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Roll back a skill to a previous version."""
    _guard("skillopt.local_rollback")
    from shogun.services.skill_rollback_service import SkillRollbackService

    svc = SkillRollbackService(db)
    result = await svc.rollback(skill_id, target_version_id=request.target_version_id)
    if result["status"] == "error":
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/local/skills/{skill_id}/quarantine")
async def quarantine_local_skill(
    skill_id: uuid.UUID,
    request: QuarantineRequest,
    db: AsyncSession = Depends(get_db),
):
    """Quarantine the active version of a skill."""
    _guard("skillopt.local_versions")
    from shogun.services.enterprise_transformation_skill import ProtectedSkillMutationError
    from shogun.services.skillopt.versioning import SkillVersionService

    svc = SkillVersionService(db)
    try:
        active = await svc.quarantine_version(skill_id, reason=request.reason)
        return {
            "status": "quarantined",
            "version_id": str(active.id),
            "version_number": active.version_number,
        }
    except ProtectedSkillMutationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(e))


@router.post("/local/skills/{skill_id}/unquarantine")
async def unquarantine_local_skill(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Remove quarantine from the active version of a skill."""
    _guard("skillopt.local_versions")
    from shogun.services.enterprise_transformation_skill import ProtectedSkillMutationError
    from shogun.services.skillopt.versioning import SkillVersionService

    svc = SkillVersionService(db)
    try:
        ver = await svc.unquarantine_version(skill_id)
        return {
            "status": "active",
            "version_id": str(ver.id),
            "version_number": ver.version_number,
        }
    except ProtectedSkillMutationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        status_code = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(e))


@router.get("/local/skills/{skill_id}/staleness")
async def check_skill_staleness(
    skill_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Check active version for tool schema drift/staleness (§20)."""
    _guard("skillopt.local_versions")
    from shogun.services.skillopt.versioning import SkillVersionService

    svc = SkillVersionService(db)
    active, warnings = await svc.get_active_with_staleness_check(skill_id)
    return {
        "skill_id": str(skill_id),
        "has_stale_tools": len(warnings) > 0,
        "warnings": warnings,
    }


# ══════════════════════════════════════════════════════════════
# REGRESSION ENDPOINTS (§25 — Regression)
# ══════════════════════════════════════════════════════════════


@router.post("/regression/suites")
async def create_regression_suite(
    request: RegressionSuiteRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create a new regression test suite."""
    _guard("skillopt.regression")
    from shogun.services.skillopt.regression import RegressionService

    svc = RegressionService(db)
    try:
        suite = await svc.create_suite(
            skill_id=request.skill_id,
            name=request.name,
            description=request.description,
            minimum_pass_rate=request.minimum_pass_rate,
        )
        return {"id": str(suite.id), "name": suite.name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/regression/suites")
async def list_regression_suites(
    skill_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List regression suites."""
    _guard("skillopt.regression")
    from shogun.services.skillopt.regression import RegressionService

    svc = RegressionService(db)
    suites = await svc.list_suites(skill_id=skill_id)
    return [
        {
            "id": str(s.id),
            "skill_id": str(s.skill_id),
            "name": s.name,
            "case_count": s.case_count,
            "last_pass_rate": s.last_pass_rate,
            "last_run_at": s.last_run_at.isoformat() if s.last_run_at else None,
            "status": s.status,
        }
        for s in suites
    ]


@router.post("/regression/suites/{suite_id}/cases")
async def add_regression_case(
    suite_id: uuid.UUID,
    request: RegressionCaseRequest,
    db: AsyncSession = Depends(get_db),
):
    """Add a test case to a regression suite."""
    _guard("skillopt.regression")
    from shogun.services.skillopt.regression import RegressionService

    svc = RegressionService(db)
    try:
        case = await svc.add_case(
            suite_id=suite_id,
            case_id=request.case_id,
            name=request.name,
            description=request.description,
            input_json=request.input_json,
            expected_output_json=request.expected_output_json,
            evaluation_criteria_json=request.evaluation_criteria_json,
            tags=request.tags,
        )
        return {"id": str(case.id), "case_id": case.case_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/regression/suites/{suite_id}/run")
async def run_regression_suite(
    suite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Execute a regression suite."""
    _guard("skillopt.regression")
    from shogun.services.skillopt.regression import RegressionService

    svc = RegressionService(db)
    try:
        run = await svc.run_suite(suite_id)
        return {
            "id": str(run.id),
            "status": run.status,
            "message": (
                "Automated regression suite execution is unavailable in this release. "
                "Suite and cases are preserved for local inspection."
            ),
            "total_cases": run.total_cases,
            "passed_cases": run.passed_cases,
            "failed_cases": run.failed_cases,
            "pass_rate": run.pass_rate,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ══════════════════════════════════════════════════════════════
# BENCHMARK ENDPOINTS (§25 — Benchmark)
# ══════════════════════════════════════════════════════════════


@router.post("/benchmarks")
async def create_benchmark(
    request: BenchmarkRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create and start a model benchmark run."""
    _guard("skillopt.local_benchmark")
    from shogun.services.skillopt.benchmark import BenchmarkService

    svc = BenchmarkService(db)
    try:
        run = await svc.create_benchmark(
            skill_id=request.skill_id,
            model_ids=request.model_ids,
            regression_suite_id=request.regression_suite_id,
            skill_version_id=request.skill_version_id,
        )
        # Attempt benchmark execution (returns unavailable)
        run = await svc.run_benchmark(run.id)
        return {
            "id": str(run.id),
            "status": run.status,
            "message": "Model benchmark execution is unavailable in this release.",
            "summary": run.summary_json,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/benchmarks/{benchmark_id}")
async def get_benchmark(
    benchmark_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get benchmark results."""
    _guard("skillopt.local_benchmark")
    from shogun.services.skillopt.benchmark import BenchmarkService

    svc = BenchmarkService(db)
    result = await svc.get_benchmark(benchmark_id)
    if not result:
        raise HTTPException(status_code=404, detail="Benchmark not found")
    return result


# ══════════════════════════════════════════════════════════════
# CAPABILITY FLAGS ENDPOINT
# ══════════════════════════════════════════════════════════════


@router.get("/capabilities")
async def get_capabilities():
    """Return all SkillOpt capability flags for the current edition."""
    caps = CapabilityService.get()
    all_flags = caps.get_all_flags()
    return {
        "edition": "yellow_label",
        "capabilities": {k: caps.enabled(k) for k in all_flags},
    }
