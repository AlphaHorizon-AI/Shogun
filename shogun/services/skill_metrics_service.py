"""Skill Metrics Service — Order 15.

Aggregates and queries performance metrics for skills.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skill_metrics import SkillMetrics


class SkillMetricsService:
    """Aggregated performance tracking for skill versions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, skill_id: uuid.UUID, version: str) -> SkillMetrics:
        """Get or create a metrics record for a skill+version pair."""
        stmt = select(SkillMetrics).where(
            SkillMetrics.skill_id == skill_id,
            SkillMetrics.version == version,
        )
        result = await self.session.execute(stmt)
        metrics = result.scalars().first()
        if not metrics:
            metrics = SkillMetrics(
                id=uuid.uuid4(),
                skill_id=skill_id,
                version=version,
            )
            self.session.add(metrics)
            await self.session.flush()
            await self.session.refresh(metrics)
        return metrics

    async def record_usage(
        self,
        skill_id: uuid.UUID,
        version: str,
        outcome: str,
        score: float | None = None,
    ) -> SkillMetrics:
        """Record a usage event and update aggregate metrics."""
        metrics = await self.get_or_create(skill_id, version)
        metrics.usage_count += 1
        if outcome == "success":
            metrics.success_count += 1
        elif outcome == "failure":
            metrics.failure_count += 1
        metrics.last_used_at = datetime.now(timezone.utc)

        # Recompute acceptance rate
        total = metrics.success_count + metrics.failure_count
        if total > 0:
            metrics.user_acceptance_rate = round(metrics.success_count / total, 4)

        # Recompute average verification score
        if score is not None:
            if metrics.average_verification_score is None:
                metrics.average_verification_score = score
            else:
                # Running average
                n = metrics.usage_count
                metrics.average_verification_score = round(
                    ((metrics.average_verification_score * (n - 1)) + score) / n, 4
                )

        # Also update the skill-level counters
        skill = await self.session.get(Skill, skill_id)
        if skill:
            skill.usage_count = metrics.usage_count
            skill.success_count = metrics.success_count
            skill.failure_count = metrics.failure_count
            skill.last_used_at = metrics.last_used_at
            if skill.lifecycle_state == "active":
                skill.lifecycle_state = "observed"

        await self.session.flush()
        return metrics

    async def get_metrics(
        self, skill_id: uuid.UUID, version: str | None = None
    ) -> dict | list[dict]:
        """Get metrics for a skill. If version is None, returns all versions."""
        if version:
            metrics = await self.get_or_create(skill_id, version)
            return self._to_dict(metrics)

        stmt = select(SkillMetrics).where(SkillMetrics.skill_id == skill_id)
        result = await self.session.execute(stmt)
        return [self._to_dict(m) for m in result.scalars().all()]

    async def get_underperforming(self, threshold: float = 0.7) -> list[dict]:
        """Return skills with acceptance rate below threshold."""
        stmt = select(SkillMetrics).where(
            SkillMetrics.user_acceptance_rate.isnot(None),
            SkillMetrics.user_acceptance_rate < threshold,
            SkillMetrics.usage_count >= 5,  # Need minimum data
        )
        result = await self.session.execute(stmt)
        return [self._to_dict(m) for m in result.scalars().all()]

    @staticmethod
    def _to_dict(m: SkillMetrics) -> dict:
        return {
            "id": str(m.id),
            "skill_id": str(m.skill_id),
            "version": m.version,
            "usage_count": m.usage_count,
            "success_count": m.success_count,
            "failure_count": m.failure_count,
            "average_verification_score": m.average_verification_score,
            "user_acceptance_rate": m.user_acceptance_rate,
            "average_retry_count": m.average_retry_count,
            "last_used_at": m.last_used_at.isoformat() if m.last_used_at else None,
            "last_optimized_at": m.last_optimized_at.isoformat() if m.last_optimized_at else None,
        }
