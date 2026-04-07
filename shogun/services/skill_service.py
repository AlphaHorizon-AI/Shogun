"""Skill service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.skill import Skill
from shogun.db.models.skill_source import SkillSource
from shogun.db.models.skill_installation import SkillInstallation
from shogun.services.base_service import BaseService

import uuid


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
