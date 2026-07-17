"""Skill Candidate Generation Service."""

import uuid
import os
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import SkillOptCandidate, SkillOptTrainingRun, SkillVersion
from shogun.services.base_service import BaseService
from shogun.config import settings


class SkillCandidateEditor(BaseService):
    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session)

    async def generate_candidate(
        self,
        training_run_id: uuid.UUID,
        instructions: str,
        base_content: str,
    ) -> SkillOptCandidate:
        """Generate a candidate skill version using LLM editing."""
        run = await self.db.get(SkillOptTrainingRun, training_run_id)
        if not run:
            raise ValueError(f"Training run {training_run_id} not found")

        # Mock LLM generation for the candidate content
        candidate_content = base_content + f"\n\n# Optimized Section\n{instructions}\n"
        
        # Save to disk
        candidate_id = uuid.uuid4()
        skill = await self.db.get(Skill, run.skill_id)
        
        # Ensure directories exist
        candidates_dir = settings.vault_path / "skills" / "candidates"
        os.makedirs(candidates_dir, exist_ok=True)
        
        content_path = str(candidates_dir / f"{skill.slug}_{candidate_id}.md")
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(candidate_content)
            
        diff_path = str(candidates_dir / f"{skill.slug}_{candidate_id}.diff")
        with open(diff_path, "w", encoding="utf-8") as f:
            f.write("mock diff content")

        candidate = SkillOptCandidate(
            id=candidate_id,
            training_run_id=run.id,
            skill_id=run.skill_id,
            base_version_id=run.base_version_id,
            candidate_content_path=content_path,
            candidate_diff_path=diff_path,
            status="pending_validation"
        )
        self.db.add(candidate)
        await self.db.commit()
        await self.db.refresh(candidate)
        return candidate
