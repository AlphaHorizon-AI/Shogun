"""Skill Promotion Service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import SkillOptCandidate
from shogun.services.base_service import BaseService
from shogun.services.skillopt.versioning import SkillVersionService


class SkillPromotionService(BaseService):
    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session)
        self.version_service = SkillVersionService(db_session)

    async def promote_candidate(self, candidate_id: uuid.UUID, created_by: str = "system") -> bool:
        """Promote a successful candidate to the active version of a skill."""
        candidate = await self.db.get(SkillOptCandidate, candidate_id)
        if not candidate:
            return False

        if candidate.status != "validated" or not candidate.validation_score:
            raise ValueError("Candidate must be successfully validated before promotion")

        # Read the candidate content
        try:
            with open(candidate.candidate_content_path, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            raise ValueError(f"Candidate content file not found at {candidate.candidate_content_path}")

        # Create a new version
        new_version = await self.version_service.create_new_version(
            skill_id=candidate.skill_id,
            parent_version_id=candidate.base_version_id,
            content_path=candidate.candidate_content_path,
            content=content,
            status="active",
            created_by=created_by
        )

        # Update the active version on the skill
        skill = await self.db.get(Skill, candidate.skill_id)
        skill.active_version_id = new_version.id

        # Update candidate status
        candidate.status = "promoted"
        await self.db.commit()
        return True

    async def reject_candidate(self, candidate_id: uuid.UUID, reason: str) -> bool:
        """Reject a candidate."""
        candidate = await self.db.get(SkillOptCandidate, candidate_id)
        if not candidate:
            return False
            
        candidate.status = "rejected"
        candidate.rejection_reason = reason
        await self.db.commit()
        return True
