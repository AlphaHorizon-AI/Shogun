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
            from shogun.services.model_reasoning import validate_model_reasoning_config

            config = dict(kwargs["config"] or {})
            provider_type = kwargs.get("provider_type")
            config["model_reasoning"] = validate_model_reasoning_config(
                str(getattr(provider_type, "value", provider_type) or ""), config
            )
            kwargs["config"] = config
            kwargs["config"] = protect_provider_config(kwargs["config"])
        return await super().create(**kwargs)

    async def update(self, record_id: uuid.UUID, **kwargs) -> ModelProvider | None:
        current = await self.get_by_id(record_id)
        if current is None:
            return None
        requested_auth = kwargs.get("auth_type", current.auth_type)
        requested_auth = str(getattr(requested_auth, "value", requested_auth))
        current_auth = str(getattr(current.auth_type, "value", current.auth_type))
        if requested_auth != current_auth and "config" not in kwargs:
            kwargs["config"] = dict(current.config or {})
        if "config" in kwargs and kwargs["config"] is not None:
            from shogun.services.model_reasoning import validate_model_reasoning_config

            config = dict(kwargs["config"] or {})
            config["model_reasoning"] = validate_model_reasoning_config(current.provider_type, config)
            kwargs["config"] = config
            retained_config = dict(current.config or {})
            if requested_auth != current_auth:
                disallowed = {
                    "api_key": {"token", "access_token", "refresh_token", "oauth_client_secret"},
                    "token": {"api_key", "api-key", "access_token", "refresh_token", "oauth_client_secret"},
                    "oauth": {"api_key", "api-key", "token"},
                    "chatgpt": {
                        "api_key",
                        "api-key",
                        "token",
                        "access_token",
                        "refresh_token",
                        "oauth_client_secret",
                    },
                    "none": {
                        "api_key",
                        "api-key",
                        "token",
                        "access_token",
                        "refresh_token",
                        "oauth_client_secret",
                    },
                }.get(requested_auth, set())
                config = {key: value for key, value in config.items() if key.casefold() not in disallowed}
                retained_config = {
                    key: value for key, value in retained_config.items() if key.casefold() not in disallowed
                }
            kwargs["config"] = protect_provider_config(config, retained_config)
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
        from shogun.services.model_router import is_automatic_profile_name

        if is_automatic_profile_name(kwargs.get("name")):
            raise ValueError("Built-in routing profile names are reserved and read-only")
        await self._validate_model_settings(kwargs.get("model_settings"))
        if kwargs.get("is_default"):
            await self.session.execute(
                sa_update(ModelRoutingProfile).values(is_default=False)
            )
        return await super().create(**kwargs)

    async def update(self, record_id: uuid.UUID, **kwargs) -> ModelRoutingProfile | None:
        from shogun.services.model_router import is_automatic_profile_name

        current = await self.get_by_id(record_id)
        if current is None:
            return None
        if is_automatic_profile_name(current.name) and set(kwargs) - {"model_settings"}:
            raise ValueError("Built-in routing profiles are read-only except for profile-scoped model settings")
        if "name" in kwargs and is_automatic_profile_name(kwargs.get("name")):
            raise ValueError("Built-in routing profile names are reserved")
        if "model_settings" in kwargs:
            await self._validate_model_settings(kwargs.get("model_settings"))
        if kwargs.get("is_default"):
            await self.session.execute(
                sa_update(ModelRoutingProfile)
                .where(ModelRoutingProfile.id != record_id)
                .values(is_default=False)
            )
        return await super().update(record_id, **kwargs)

    async def _validate_model_settings(self, settings: dict | None) -> None:
        if not settings:
            return
        from shogun.db.models.model_router import ModelRegistryEntry
        from shogun.services.model_reasoning import validate_reasoning_effort

        for registry_key, raw in settings.items():
            values = raw.model_dump() if hasattr(raw, "model_dump") else dict(raw or {})
            effort = values.get("reasoning_effort")
            if not effort:
                continue
            try:
                registry_id = uuid.UUID(str(registry_key))
            except ValueError:
                registry_id = None
            item = await self.session.get(ModelRegistryEntry, registry_id) if registry_id else None
            if item is None:
                result = await self.session.execute(
                    select(ModelRegistryEntry).where(ModelRegistryEntry.model_id == str(registry_key)).limit(1)
                )
                item = result.scalars().first()
            if item is None:
                raise ValueError(f"Reasoning settings reference unknown registry model {registry_key!r}")
            validate_reasoning_effort(item.provider, item.model_id, str(effort))

    async def delete(self, record_id: uuid.UUID) -> bool:
        from shogun.services.model_router import is_automatic_profile_name

        current = await self.get_by_id(record_id)
        if current is None:
            return False
        if is_automatic_profile_name(current.name):
            raise ValueError("Built-in routing profiles cannot be deleted")
        return await super().delete(record_id)
