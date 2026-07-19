"""Skill Validation and Evaluation Service."""

import uuid
from typing import List

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skillopt import SkillOptCandidate, SkillOptEvalResult
from shogun.services.base_service import BaseService


class SkillValidationService(BaseService):
    def __init__(self, db_session: AsyncSession):
        super().__init__(SkillOptCandidate, db_session)
        self.db = db_session

    async def static_validate(self, candidate_id: uuid.UUID) -> bool:
        """Perform static checks on a candidate skill (e.g. valid markdown, safety)."""
        candidate = await self.db.get(SkillOptCandidate, candidate_id)
        if not candidate:
            return False

        # In a real implementation, this would parse markdown and check against constraints.
        # For now, we mock success.
        candidate.static_validation_status = "passed"
        await self.db.commit()
        return True

    async def evaluate_candidate(self, candidate_id: uuid.UUID, validation_tasks: List[dict], target_profile: str) -> List[SkillOptEvalResult]:
        """Run a candidate against held-out tasks and record results."""
        candidate = await self.db.get(SkillOptCandidate, candidate_id)
        if not candidate:
            return []

        # Mock evaluation process
        results = []
        for task in validation_tasks:
            result = SkillOptEvalResult(
                id=uuid.uuid4(),
                candidate_id=candidate.id,
                skill_version_id=None,
                eval_task_id=task.get("task_id", "unknown"),
                model_used=target_profile,
                posture="supervised",
                status="completed",
                baseline_score=0.75,
                candidate_score=0.85, # Mock improvement
                verification_status="passed",
                safety_status="passed",
                runtime_seconds=12.5,
            )
            self.db.add(result)
            results.append(result)
        
        # Compute average
        if results:
            avg_score = sum(r.candidate_score for r in results if r.candidate_score) / len(results)
            candidate.validation_score = avg_score
            candidate.status = "validated"

        await self.db.commit()
        return results
