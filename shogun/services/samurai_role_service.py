"""Samurai Role service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.samurai_role import SamuraiRole
from shogun.services.base_service import BaseService


class SamuraiRoleService(BaseService[SamuraiRole]):
    def __init__(self, session: AsyncSession):
        super().__init__(SamuraiRole, session)

    async def get_by_slug(self, slug: str) -> SamuraiRole | None:
        result = await self.session.execute(
            select(SamuraiRole).where(SamuraiRole.slug == slug)
        )
        return result.scalars().first()
