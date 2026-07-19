"""Skill Promotion Service."""

import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import SkillOptCandidate
from shogun.services.base_service import BaseService
from shogun.services.skillopt.versioning import SkillVersionService


class SkillPromotionService(BaseService):
    def __init__(self, db_session: AsyncSession):
        super().__init__(SkillOptCandidate, db_session)
        self.db = db_session
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
            with open(candidate.candidate_content_path, encoding="utf-8") as f:
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
        # The promoted Markdown becomes the canonical skill instructions.
        # Archives is refreshed below, and runtime activation reads from there.
        skill.body_text = content
        skill.local_path = candidate.candidate_content_path
        skill.hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        skill.brief_text = None
        manifest = dict(skill.manifest or {})
        manifest["canonical_content_source"] = "skills_archive"
        manifest["canonical_content_hash"] = skill.hash
        manifest["canonical_content_length"] = len(content)
        manifest["optimized_by"] = "skillopt"
        manifest["active_version"] = new_version.version_number
        skill.manifest = manifest

        # Update candidate status
        candidate.status = "promoted"
        await self.db.flush()
        from shogun.services.skill_memory_sync import sync_skills_to_all_agent_memories

        await sync_skills_to_all_agent_memories(self.db)
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
