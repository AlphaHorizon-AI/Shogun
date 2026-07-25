"""Model service — providers, definitions, and routing profiles."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.model_definition import ModelDefinition
from shogun.db.models.model_provider import ModelProvider
from shogun.db.models.model_routing import ModelRoutingProfile
from shogun.services.base_service import BaseService
from shogun.services.provider_credentials import protect_provider_config


class ModelProviderService(BaseService[ModelProvider]):
    def __init__(self, session: AsyncSession):
        super().__init__(ModelProvider, session)

    async def get_by_slug(self, slug: str) -> ModelProvider | None:
        result = await self.session.execute(
            select(ModelProvider).where(ModelProvider.slug == slug)
        )
        return result.scalars().first()

    async def create(self, **kwargs) -> ModelProvider:
        if "config" in kwargs:
            kwargs["config"] = protect_provider_config(kwargs["config"])
        return await super().create(**kwargs)

    async def update(self, record_id: uuid.UUID, **kwargs) -> ModelProvider | None:
        if "config" in kwargs and kwargs["config"] is not None:
            current = await self.get_by_id(record_id)
            if current is None:
                return None
            kwargs["config"] = protect_provider_config(kwargs["config"], current.config)
        return await super().update(record_id, **kwargs)


class ModelDefinitionService(BaseService[ModelDefinition]):
    def __init__(self, session: AsyncSession):
        super().__init__(ModelDefinition, session)

    async def get_by_provider(self, provider_id: uuid.UUID) -> list[ModelDefinition]:
        result = await self.session.execute(
            select(ModelDefinition).where(ModelDefinition.provider_id == provider_id)
        )
        return list(result.scalars().all())


class ModelRoutingProfileService(BaseService[ModelRoutingProfile]):
    def __init__(self, session: AsyncSession):
        super().__init__(ModelRoutingProfile, session)

    async def get_default(self) -> ModelRoutingProfile | None:
        result = await self.session.execute(
            select(ModelRoutingProfile)
            .where(ModelRoutingProfile.is_default.is_(True))
            .order_by(ModelRoutingProfile.updated_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def create(self, **kwargs) -> ModelRoutingProfile:
        if kwargs.get("is_default"):
            await self.session.execute(
                sa_update(ModelRoutingProfile).values(is_default=False)
            )
        return await super().create(**kwargs)

    async def update(self, record_id: uuid.UUID, **kwargs) -> ModelRoutingProfile | None:
        if kwargs.get("is_default"):
            await self.session.execute(
                sa_update(ModelRoutingProfile)
                .where(ModelRoutingProfile.id != record_id)
                .values(is_default=False)
            )
        return await super().update(record_id, **kwargs)
