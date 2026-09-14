"""Benchmark Service — local model benchmarking against regression suites.

Implements §15–§16 of the build paper. Tests supported models against
the same local regression suite using identical fixtures, tool definitions,
evaluator, skill version, and policy snapshot.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skillopt import (
    SkillOptBenchmarkResult,
    SkillOptBenchmarkRun,
    SkillOptCompetenceProfile,
    SkillOptRegressionSuite,
)
from shogun.services.base_service import BaseService
from shogun.services.capability_service import CapabilityService

logger = logging.getLogger(__name__)


class BenchmarkService(BaseService):
    """Manages model benchmark runs and local competence profiles."""

    def __init__(self, db_session: AsyncSession):
        super().__init__(SkillOptBenchmarkRun, db_session)
        self.db = db_session

    # ── Create benchmark ─────────────────────────────────────

    async def create_benchmark(
        self,
        skill_id: uuid.UUID,
        model_ids: list[str],
        regression_suite_id: uuid.UUID,
        *,
        skill_version_id: uuid.UUID | None = None,
    ) -> SkillOptBenchmarkRun:
        """Create a new model benchmark run.

        The benchmark will run the specified regression suite against each
        model in ``model_ids`` using identical conditions.
        """
        CapabilityService.get().require("skillopt.local_benchmark")

        if len(model_ids) < 2:
            raise ValueError("Benchmark requires at least 2 models to compare")

        suite = await self.db.get(SkillOptRegressionSuite, regression_suite_id)
        if not suite:
            raise ValueError(f"Regression suite {regression_suite_id} not found")

        run = SkillOptBenchmarkRun(
            id=uuid.uuid4(),
            skill_id=skill_id,
            regression_suite_id=regression_suite_id,
            skill_version_id=skill_version_id,
            model_ids_json=model_ids,
            status="pending",
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        _emit_audit(
            "skillopt.benchmark.started",
            f"Benchmark created: {len(model_ids)} models vs suite '{suite.name}'",
            detail={
                "benchmark_id": str(run.id),
                "model_ids": model_ids,
                "suite_id": str(regression_suite_id),
            },
        )
        return run

    # ── Execute benchmark ────────────────────────────────────

    async def run_benchmark(self, benchmark_id: uuid.UUID) -> SkillOptBenchmarkRun:
        """Execute a benchmark run — tests each model against the suite.

        Model benchmark execution is unavailable in this release.
        Marks the run as unavailable without generating random results
        or writing fake competence profiles.
        """
        run = await self.db.get(SkillOptBenchmarkRun, benchmark_id)
        if not run:
            raise ValueError(f"Benchmark {benchmark_id} not found")

        now = datetime.now(timezone.utc)
        run.status = "unavailable"
        run.started_at = now
        run.completed_at = now
        run.summary_json = {
            "status": "unavailable",
            "error": "EXECUTION_UNAVAILABLE",
            "message": "Model benchmark execution is unavailable in this release.",
        }

        await self.db.commit()

        _emit_audit(
            "skillopt.benchmark.unavailable",
            f"Benchmark {benchmark_id} execution unavailable in this release",
            detail={
                "benchmark_id": str(benchmark_id),
                "status": run.status,
            },
        )
        return run

    # ── Competence profiles ──────────────────────────────────

    async def get_competence_profile(
        self, model_id: str, skill_id: uuid.UUID | None = None
    ) -> list[SkillOptCompetenceProfile]:
        """Retrieve local competence profiles for a model."""
        stmt = select(SkillOptCompetenceProfile).where(SkillOptCompetenceProfile.model_id == model_id)
        if skill_id:
            stmt = stmt.where(SkillOptCompetenceProfile.skill_id == skill_id)
        stmt = stmt.order_by(SkillOptCompetenceProfile.evaluated_at.desc())

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Get benchmark ────────────────────────────────────────

    async def get_benchmark(self, benchmark_id: uuid.UUID) -> dict[str, Any] | None:
        """Get a benchmark run with its per-model results."""
        run = await self.db.get(SkillOptBenchmarkRun, benchmark_id)
        if not run:
            return None

        stmt = select(SkillOptBenchmarkResult).where(SkillOptBenchmarkResult.benchmark_run_id == benchmark_id)
        result = await self.db.execute(stmt)
        model_results = list(result.scalars().all())

        return {
            "id": str(run.id),
            "skill_id": str(run.skill_id),
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "models": [
                {
                    "model_id": r.model_id,
                    "success_rate": r.success_rate,
                    "policy_compliance": r.policy_compliance,
                    "avg_tool_calls": r.avg_tool_calls,
                    "avg_latency_seconds": r.avg_latency_seconds,
                    "avg_cost_eur": r.avg_cost_eur,
                    "total_cases": r.total_cases,
                    "passed_cases": r.passed_cases,
                }
                for r in model_results
            ],
            "summary": run.summary_json,
        }

    # ── Internal ─────────────────────────────────────────────

    async def _benchmark_model(
        self,
        run: SkillOptBenchmarkRun,
        model_id: str,
        index: int,
    ) -> SkillOptBenchmarkResult:
        """Run a single model against the benchmark's regression suite.

        Model benchmarking execution is unavailable in this release.
        """
        raise NotImplementedError("Model benchmarking execution is unavailable in this release.")

    async def _update_competence_profile(
        self,
        model_id: str,
        skill_id: uuid.UUID,
        result: SkillOptBenchmarkResult,
    ) -> None:
        """Create or update a local competence profile for a model+skill."""
        # Find existing profile
        stmt = select(SkillOptCompetenceProfile).where(
            SkillOptCompetenceProfile.model_id == model_id,
            SkillOptCompetenceProfile.skill_id == skill_id,
        )
        existing = await self.db.execute(stmt)
        profile = existing.scalars().first()

        if profile:
            profile.success_rate = result.success_rate
            profile.policy_compliance = result.policy_compliance
            profile.avg_tool_calls = result.avg_tool_calls
            profile.avg_latency_seconds = result.avg_latency_seconds
            profile.avg_cost_eur = result.avg_cost_eur
            profile.evaluated_at = datetime.now(timezone.utc)
        else:
            profile = SkillOptCompetenceProfile(
                id=uuid.uuid4(),
                model_id=model_id,
                skill_id=skill_id,
                success_rate=result.success_rate,
                policy_compliance=result.policy_compliance,
                avg_tool_calls=result.avg_tool_calls,
                avg_latency_seconds=result.avg_latency_seconds,
                avg_cost_eur=result.avg_cost_eur,
                evaluated_at=datetime.now(timezone.utc),
            )
            self.db.add(profile)


# ── Audit helper ─────────────────────────────────────────────


def _emit_audit(
    event_type: str,
    action: str,
    *,
    detail: dict | None = None,
    severity: str = "info",
) -> None:
    """Emit to the immutable audit chain."""
    try:
        from shogun.services.immutable_audit import append

        append(
            event_id=str(uuid.uuid4()),
            event_category="skillopt",
            event_type=event_type,
            action=action,
            severity=severity,
            detail=detail,
        )
    except Exception as exc:
        logger.warning("Audit emit failed for %s: %s", event_type, exc)
