"""SkillOpt Lab Service — main orchestrator for proactive skill optimization.

Implements the full optimization loop (§14): candidate proposal → ToolGate
preflight → safe execution → evaluation → textual gradient → candidate
update → repeat until budget exhausted or acceptance criteria met.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import (
    SkillOptLabRun,
)
from shogun.services.base_service import BaseService
from shogun.services.capability_service import CapabilityService

logger = logging.getLogger(__name__)


class SkillOptLabService(BaseService):
    """Orchestrates proactive tool-chain optimization runs."""

    def __init__(self, db_session: AsyncSession):
        super().__init__(SkillOptLabRun, db_session)
        self.db = db_session

    # ── Create ───────────────────────────────────────────────

    async def create_lab_run(
        self,
        skill_id: uuid.UUID,
        *,
        optimizer_model: str = "high_capability",
        execution_mode: str = "mock",
        max_iterations: int = 10,
        max_llm_calls: int = 40,
        max_tool_calls: int = 100,
        max_runtime_seconds: int = 900,
        max_cost_eur: float = 5.0,
        config: dict[str, Any] | None = None,
    ) -> SkillOptLabRun:
        """Create and persist a new Lab optimization run.

        Validates that the skill exists, has an active version, and that
        the ``skillopt.lab`` capability is enabled.
        """
        CapabilityService.get().require("skillopt.lab")

        skill = await self.db.get(Skill, skill_id)
        if not skill or not skill.active_version_id:
            raise ValueError("Skill not found or has no active version")

        run = SkillOptLabRun(
            id=uuid.uuid4(),
            skill_id=skill_id,
            base_version_id=skill.active_version_id,
            status="pending",
            optimizer_model=optimizer_model,
            execution_mode=execution_mode,
            max_iterations=max_iterations,
            max_llm_calls=max_llm_calls,
            max_tool_calls=max_tool_calls,
            max_runtime_seconds=max_runtime_seconds,
            max_cost_eur=max_cost_eur,
            config_json=config or {},
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)

        # Immutable audit
        _emit_audit(
            "skillopt.lab.run.created",
            f"Lab run created for skill {skill.name!r}",
            detail={"run_id": str(run.id), "skill_id": str(skill_id)},
        )
        return run

    # ── Execute ──────────────────────────────────────────────

    async def execute_lab_run(self, run_id: uuid.UUID) -> SkillOptLabRun:
        """Execute the full optimization loop for a Lab run.

        Proactive optimizer execution is unavailable in this release.
        Marks the run clearly as unavailable without fabricating scores or
        fake resource usage.
        """
        run = await self.db.get(SkillOptLabRun, run_id)
        if not run:
            raise ValueError(f"Lab run {run_id} not found")

        run.status = "unavailable"
        run.started_at = datetime.now(timezone.utc)
        run.completed_at = run.started_at
        run.result_json = {
            "status": "unavailable",
            "error": "EXECUTION_UNAVAILABLE",
            "message": (
                "SkillOpt Lab proactive optimization execution is not available in this release. "
                "Local skill management and configuration are available."
            ),
        }
        await self.db.commit()

        _emit_audit(
            "skillopt.lab.run.unavailable",
            f"Lab run {run_id} execution unavailable in this release",
            detail={"run_id": str(run_id), "status": run.status},
        )
        return run

    # ── Cancel ───────────────────────────────────────────────

    async def cancel_lab_run(self, run_id: uuid.UUID) -> SkillOptLabRun:
        """Cancel a running Lab run."""
        run = await self.db.get(SkillOptLabRun, run_id)
        if not run:
            raise ValueError(f"Lab run {run_id} not found")
        if run.status not in ("pending", "running"):
            raise ValueError(f"Lab run {run_id} is already {run.status}")

        run.status = "cancelled"
        run.completed_at = datetime.now(timezone.utc)
        await self.db.commit()
        return run

    # ── List ─────────────────────────────────────────────────

    async def list_runs(
        self,
        skill_id: uuid.UUID | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[SkillOptLabRun]:
        """List Lab runs, optionally filtered by skill or status."""
        stmt = select(SkillOptLabRun).order_by(SkillOptLabRun.created_at.desc())
        if skill_id:
            stmt = stmt.where(SkillOptLabRun.skill_id == skill_id)
        if status:
            stmt = stmt.where(SkillOptLabRun.status == status)
        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # ── Internal ─────────────────────────────────────────────

    def _budget_exceeded(self, run: SkillOptLabRun) -> bool:
        """Check whether any budget limit has been exceeded."""
        if run.total_llm_calls >= run.max_llm_calls:
            return True
        if run.total_tool_calls >= run.max_tool_calls:
            return True
        if run.total_cost_eur >= run.max_cost_eur:
            return True
        elapsed = (datetime.now(timezone.utc) - run.started_at).total_seconds() if run.started_at else 0
        if elapsed >= run.max_runtime_seconds:
            return True
        return False

    async def _run_iteration(self, run: SkillOptLabRun, iteration: int) -> dict[str, Any]:
        """Optimization iteration execution is unavailable in this release."""
        raise NotImplementedError(
            "SkillOpt Lab automated optimizer iteration is not implemented in this release."
        )


# ── Audit helper ─────────────────────────────────────────────


def _emit_audit(
    event_type: str,
    action: str,
    *,
    detail: dict | None = None,
    severity: str = "info",
) -> None:
    """Emit to the immutable audit chain. Failures are logged, not raised."""
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
