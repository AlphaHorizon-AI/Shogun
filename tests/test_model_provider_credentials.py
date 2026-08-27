from __future__ import annotations

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.db.base import Base
from shogun.engine.flow_engine import _provider_connection
from shogun.schemas.common import ProviderType
from shogun.services.model_service import ModelProviderService
from shogun.services.provider_credentials import protect_provider_config, provider_api_key


async def test_provider_edit_without_secret_preserves_stored_credential() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        service = ModelProviderService(session)
        provider = await service.create(
            provider_type="openrouter",
            name="vendor/model",
            slug="vendor-model",
            base_url="https://openrouter.ai/api/v1",
            auth_type="api_key",
            is_local=False,
            status="connected",
            config={"api_key": "original-secret"},
        )
        encrypted_secret = provider.config["api_key"]

        updated = await service.update(
            provider.id,
            name="Renamed provider",
            config={"models": ["vendor/model"]},
        )

        assert updated is not None
        assert updated.config["api_key"] == encrypted_secret
        assert provider_api_key(updated.config) == "original-secret"
        assert _provider_connection(updated, "vendor/model")[3]["Authorization"] == "Bearer original-secret"

    await engine.dispose()


async def test_provider_edit_can_replace_stored_credential() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        service = ModelProviderService(session)
        provider = await service.create(
            provider_type="openai",
            name="OpenAI",
            slug="openai",
            base_url="https://api.openai.com/v1",
            auth_type="api_key",
            is_local=False,
            status="connected",
            config={"api_key": "old-secret", "models": ["gpt-5"]},
        )

        updated = await service.update(
            provider.id,
            config={"api_key": "new-secret", "models": ["gpt-5"]},
        )

        assert updated is not None
        assert provider_api_key(updated.config) == "new-secret"
        assert "new-secret" not in updated.config["api_key"]

    await engine.dispose()


async def test_provider_create_accepts_schema_enum_with_reasoning_defaults() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        provider = await ModelProviderService(session).create(
            provider_type=ProviderType.OPENAI,
            name="OpenAI",
            slug="openai-reasoning",
            base_url="https://api.openai.com/v1",
            auth_type="api_key",
            is_local=False,
            status="connected",
            config={
                "api_key": "secret",
                "models": ["gpt-5.6"],
                "model_reasoning": {"gpt-5.6": "high"},
            },
        )

        assert provider.config["model_reasoning"] == {"gpt-5.6": "high"}

    await engine.dispose()


async def test_switching_to_oauth_removes_old_api_key() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        service = ModelProviderService(session)
        provider = await service.create(
            provider_type="google",
            name="Gemini",
            slug="google-oauth-transition",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            auth_type="api_key",
            is_local=False,
            status="connected",
            config={"api_key": "old-api-key", "models": ["gemini-test"]},
        )

        updated = await service.update(
            provider.id,
            auth_type="oauth",
            config={"oauth_client_id": "client-id", "models": ["gemini-test"]},
        )

        assert updated is not None
        assert "api_key" not in updated.config
        assert provider_api_key(updated.config) is None

    await engine.dispose()


def test_omitted_nested_secrets_are_retained_without_stale_non_secret_config() -> None:
    existing = protect_provider_config(
        {"credentials": {"access_token": "secret", "label": "old"}, "obsolete": True}
    )

    updated = protect_provider_config({"models": ["model-a"]}, existing)

    assert provider_api_key(updated.get("credentials")) == "secret"
    assert "label" not in updated["credentials"]
    assert "obsolete" not in updated
