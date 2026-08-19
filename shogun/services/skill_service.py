"""Skill service."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skill_installation import SkillInstallation
from shogun.db.models.skill_source import SkillSource
from shogun.services.base_service import BaseService
from shogun.services.enterprise_transformation_skill import assert_skill_mutable


class SkillSourceService(BaseService[SkillSource]):
    def __init__(self, session: AsyncSession):
        super().__init__(SkillSource, session)


class SkillService(BaseService[Skill]):
    def __init__(self, session: AsyncSession):
        super().__init__(Skill, session)

    async def get_by_slug(self, slug: str) -> Skill | None:
        result = await self.session.execute(
            select(Skill).where(Skill.slug == slug, Skill.is_deleted == False)
        )
        return result.scalars().first()

    async def get_installed(self) -> list[SkillInstallation]:
        result = await self.session.execute(
            select(SkillInstallation).where(SkillInstallation.status == "installed")
        )
        return list(result.scalars().all())

    async def delete(self, record_id: uuid.UUID) -> bool:
        """Soft-delete a mutable skill while preserving protected built-ins."""
        skill = await self.get_by_id(record_id)
        if skill is None:
            return False
        assert_skill_mutable(skill, "delete")
        return await super().delete(record_id)

    async def update(self, record_id: uuid.UUID, **kwargs: Any) -> Skill | None:
        """Reject generic edits to protected kernels; bootstrap owns repairs."""
        skill = await self.get_by_id(record_id)
        if skill is None:
            return None
        assert_skill_mutable(skill, "update")
        return await super().update(record_id, **kwargs)
