"""Persona service."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.persona import Persona
from shogun.services.base_service import BaseService


class PersonaService(BaseService[Persona]):
    def __init__(self, session: AsyncSession):
        super().__init__(Persona, session)

    async def get_by_slug(self, slug: str) -> Persona | None:
        from sqlalchemy import select
        result = await self.session.execute(
            select(Persona).where(Persona.slug == slug)
        )
        return result.scalars().first()
