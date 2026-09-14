"""Regression Service — manage and execute local regression test suites.

Implements §14.8 (regression builder) and §33 (regression suite structure).
Regression suites are local to the Tenshu instance and can be used for
both skill validation and model benchmarking.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skillopt import (
    SkillOptRegressionCase,
    SkillOptRegressionRun,
    SkillOptRegressionSuite,
)
from shogun.services.base_service import BaseService
from shogun.services.capability_service import CapabilityService

logger = logging.getLogger(__name__)


class RegressionService(BaseService):
    """Manages regression suites, cases, and execution runs."""

    def __init__(self, db_session: AsyncSession):
        super().__init__(SkillOptRegressionSuite, db_session)
        self.db = db_session

    # ── Suite management ─────────────────────────────────────

    async def create_suite(
        self,
        skill_id: uuid.UUID,
        name: str,
        *,
        description: str | None = None,
        minimum_pass_rate: float = 0.95,
    ) -> SkillOptRegressionSuite:
        """Create a new regression suite for a skill."""
        CapabilityService.get().require("skillopt.regression")

        suite = SkillOptRegressionSuite(
            id=uuid.uuid4(),
            skill_id=skill_id,
            name=name,
            description=description,
            minimum_pass_rate=minimum_pass_rate,
        )
        self.db.add(suite)
        await self.db.commit()
        await self.db.refresh(suite)

        _emit_audit(
            "skillopt.regression.created",
            f"Regression suite '{name}' created for skill {skill_id}",
            detail={"suite_id": str(suite.id), "skill_id": str(skill_id)},
        )
        return suite

    async def list_suites(
        self,
        skill_id: uuid.UUID | None = None,
        limit: int = 50,
    ) -> list[SkillOptRegressionSuite]:
        """List regression suites, optionally filtered by skill."""
        stmt = select(SkillOptRegressionSuite).order_by(SkillOptRegressionSuite.created_at.desc())
        if skill_id:
            stmt = stmt.where(SkillOptRegressionSuite.skill_id == skill_id)
        stmt = stmt.limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_suite(self, suite_id: uuid.UUID) -> SkillOptRegressionSuite | None:
        """Get a single regression suite by ID."""
        return await self.db.get(SkillOptRegressionSuite, suite_id)

    # ── Case management ──────────────────────────────────────

    async def add_case(
        self,
        suite_id: uuid.UUID,
        case_id: str,
        name: str,
        *,
        description: str | None = None,
        input_json: dict[str, Any] | None = None,
        expected_output_json: dict[str, Any] | None = None,
        evaluation_criteria_json: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> SkillOptRegressionCase:
        """Add a test case to a regression suite."""
        suite = await self.db.get(SkillOptRegressionSuite, suite_id)
        if not suite:
            raise ValueError(f"Suite {suite_id} not found")

        case = SkillOptRegressionCase(
            id=uuid.uuid4(),
            suite_id=suite_id,
            case_id=case_id,
            name=name,
            description=description,
            input_json=input_json or {},
            expected_output_json=expected_output_json or {},
            evaluation_criteria_json=evaluation_criteria_json or {},
            tags=tags or [],
        )
        self.db.add(case)

        # Update case count on suite
        suite.case_count = (suite.case_count or 0) + 1

        await self.db.commit()
        await self.db.refresh(case)
        return case

    async def list_cases(self, suite_id: uuid.UUID) -> list[SkillOptRegressionCase]:
        """List all cases in a regression suite."""
        stmt = (
            select(SkillOptRegressionCase)
            .where(SkillOptRegressionCase.suite_id == suite_id)
            .order_by(SkillOptRegressionCase.case_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Suite execution ──────────────────────────────────────

    async def run_suite(
        self,
        suite_id: uuid.UUID,
        *,
        skill_version_id: uuid.UUID | None = None,
        model_used: str | None = None,
    ) -> SkillOptRegressionRun:
        """Execute all cases in a regression suite and record results.

        In the initial implementation, cases are evaluated against their
        expected outputs using deterministic comparison. The full
        implementation will integrate with the safe executor and evaluator.
        """
        CapabilityService.get().require("skillopt.regression")

        suite = await self.db.get(SkillOptRegressionSuite, suite_id)
        if not suite:
            raise ValueError(f"Suite {suite_id} not found")

        cases = await self.list_cases(suite_id)
        if not cases:
            raise ValueError(f"Suite {suite_id} has no test cases")

        now = datetime.now(timezone.utc)
        run = SkillOptRegressionRun(
            id=uuid.uuid4(),
            suite_id=suite_id,
            skill_version_id=skill_version_id,
            model_used=model_used,
            status="unavailable",
            total_cases=len(cases),
            passed_cases=0,
            failed_cases=0,
            pass_rate=None,
            started_at=now,
            completed_at=now,
            results_json=[
                {
                    "status": "unavailable",
                    "error": "EXECUTION_UNAVAILABLE",
                    "message": "Automated regression suite execution is unavailable in this release.",
                }
            ],
        )
        self.db.add(run)

        # Record run timestamp on suite without writing fictional pass rates
        suite.last_run_at = run.completed_at

        await self.db.commit()
        await self.db.refresh(run)

        _emit_audit(
            "skillopt.regression.unavailable",
            f"Regression suite '{suite.name}' execution unavailable in this release",
            detail={
                "suite_id": str(suite_id),
                "run_id": str(run.id),
                "status": run.status,
            },
        )
        return run

    async def get_suite_health(self, suite_id: uuid.UUID) -> dict[str, Any]:
        """Return the health status of a regression suite."""
        suite = await self.db.get(SkillOptRegressionSuite, suite_id)
        if not suite:
            return {"status": "not_found"}

        healthy = suite.last_pass_rate is not None and suite.last_pass_rate >= suite.minimum_pass_rate

        return {
            "suite_id": str(suite.id),
            "name": suite.name,
            "case_count": suite.case_count,
            "last_run_at": suite.last_run_at.isoformat() if suite.last_run_at else None,
            "last_pass_rate": suite.last_pass_rate,
            "minimum_pass_rate": suite.minimum_pass_rate,
            "healthy": healthy,
            "status": "healthy" if healthy else "degraded" if suite.last_pass_rate else "untested",
        }

    # ── List runs ────────────────────────────────────────────

    async def list_runs(self, suite_id: uuid.UUID, limit: int = 20) -> list[SkillOptRegressionRun]:
        """List recent regression runs for a suite."""
        stmt = (
            select(SkillOptRegressionRun)
            .where(SkillOptRegressionRun.suite_id == suite_id)
            .order_by(SkillOptRegressionRun.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


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
