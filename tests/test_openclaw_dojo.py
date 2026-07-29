from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.api.dojo import _resolve_primary_model
from shogun.db.base import Base
from shogun.db.models.model_provider import ModelProvider
from shogun.db.models.model_router import ModelRegistryEntry
from shogun.db.models.model_routing import ModelRoutingProfile


@pytest.mark.asyncio
async def test_resolve_primary_model_supports_current_routing_rule_schema():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        provider = ModelProvider(
            provider_type="ollama",
            name="Local Ollama",
            slug="local-ollama-exam",
            is_local=True,
            status="connected",
        )
        session.add(provider)
        await session.flush()
        model = ModelRegistryEntry(
            model_id="gemma4:e4b",
            display_name="Gemma 4",
            provider_id=provider.id,
            provider="ollama",
            enabled=True,
        )
        profile = ModelRoutingProfile(
            name="Exam routing",
            rules=[{
                "task_type": "*",
                "primary_model_id": str(provider.id),
                "fallback_model_ids": [],
            }],
        )
        session.add_all([model, profile])
        await session.commit()

        resolved = await _resolve_primary_model(
            SimpleNamespace(model_routing_profile_id=profile.id), session
        )

    await engine.dispose()
    assert resolved == "gemma4:e4b"
