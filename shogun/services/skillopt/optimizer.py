"""Skill Optimizer Service."""

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import SkillOptTrainingRun
from shogun.services.base_service import BaseService


class SkillOptService(BaseService):
    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session)

    async def start_training_run(
        self,
        skill_id: uuid.UUID,
        optimizer_model: str = "high_capability",
        target_model_profile: str = "balanced"
    ) -> SkillOptTrainingRun:
        """Start a new optimization run for a skill."""
        skill = await self.db.get(Skill, skill_id)
        if not skill or not skill.active_version_id:
            raise ValueError("Skill not found or has no active version")

        # Create training run
        run = SkillOptTrainingRun(
            id=uuid.uuid4(),
            skill_id=skill_id,
            base_version_id=skill.active_version_id,
            status="running",
            optimizer_model=optimizer_model,
            target_model_profile=target_model_profile,
            started_at=datetime.utcnow()
        )
        self.db.add(run)
        await self.db.commit()
        await self.db.refresh(run)
        return run

    async def complete_training_run(self, run_id: uuid.UUID, status: str = "completed") -> SkillOptTrainingRun:
        """Mark a training run as completed."""
        run = await self.db.get(SkillOptTrainingRun, run_id)
        if not run:
            raise ValueError("Run not found")
            
        run.status = status
        run.completed_at = datetime.utcnow()
        await self.db.commit()
        return run
