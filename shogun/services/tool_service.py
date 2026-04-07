"""Tool service."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.tool_connector import ToolConnector
from shogun.services.base_service import BaseService


class ToolService(BaseService[ToolConnector]):
    def __init__(self, session: AsyncSession):
        super().__init__(ToolConnector, session)

    async def get_by_slug(self, slug: str) -> ToolConnector | None:
        result = await self.session.execute(
            select(ToolConnector).where(
                ToolConnector.slug == slug,
                ToolConnector.is_deleted == False,
            )
        )
        return result.scalars().first()
