"""Skill Versioning Service."""

import uuid
import hashlib
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import SkillVersion
from shogun.services.base_service import BaseService


class SkillVersionService(BaseService):
    def __init__(self, db_session: AsyncSession):
        super().__init__(SkillVersion, db_session)
        self.db = db_session

    async def get_active_version(self, skill_id: uuid.UUID) -> Optional[SkillVersion]:
        """Get the currently active version of a skill."""
        skill = await self.db.get(Skill, skill_id)
        if not skill or not skill.active_version_id:
            return None
        return await self.db.get(SkillVersion, skill.active_version_id)

    async def get_versions(self, skill_id: uuid.UUID) -> List[SkillVersion]:
        """Get all versions of a skill."""
        stmt = select(SkillVersion).where(SkillVersion.skill_id == skill_id).order_by(SkillVersion.version_number.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create_initial_version(self, skill: Skill, content_path: str, content: str, created_by: str = "system") -> SkillVersion:
        """Create the v1 version for a skill if none exists."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Check if any version exists
        existing = await self.get_versions(skill.id)
        if existing:
            return existing[-1]  # Return the oldest (v1)

        version = SkillVersion(
            id=uuid.uuid4(),
            skill_id=skill.id,
            version_number=1,
            status="active",
            content_path=content_path,
            content_hash=content_hash,
            created_by=created_by,
        )
        self.db.add(version)
        skill.active_version_id = version.id
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def create_new_version(
        self, 
        skill_id: uuid.UUID, 
        parent_version_id: uuid.UUID, 
        content_path: str, 
        content: str, 
        status: str = "candidate",
        created_by: str = "skillopt"
    ) -> SkillVersion:
        """Create a new version (e.g. from a candidate)."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Determine next version number
        versions = await self.get_versions(skill_id)
        next_number = versions[0].version_number + 1 if versions else 1

        version = SkillVersion(
            id=uuid.uuid4(),
            skill_id=skill_id,
            version_number=next_number,
            status=status,
            content_path=content_path,
            content_hash=content_hash,
            parent_version_id=parent_version_id,
            created_by=created_by,
        )
        self.db.add(version)
        await self.db.commit()
        await self.db.refresh(version)
        return version

    async def activate_version(self, skill_id: uuid.UUID, version_id: uuid.UUID) -> SkillVersion:
        """Make a specific version the active one."""
        skill = await self.db.get(Skill, skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} not found")
            
        version = await self.db.get(SkillVersion, version_id)
        if not version:
            raise ValueError(f"SkillVersion {version_id} not found")

        # Deactivate old active version if any
        if skill.active_version_id:
            old_version = await self.db.get(SkillVersion, skill.active_version_id)
            if old_version:
                old_version.status = "archived"

        version.status = "active"
        skill.active_version_id = version.id
        await self.db.commit()
        return version
