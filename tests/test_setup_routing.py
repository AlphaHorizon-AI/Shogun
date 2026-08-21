from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.api import setup as setup_api
from shogun.api.setup import ProviderSetup, SetupCompletePayload
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.model_provider import ModelProvider
from shogun.db.models.model_router import ModelRegistryEntry
from shogun.db.models.model_routing import ModelRoutingProfile
from shogun.services import model_router


@pytest.mark.asyncio
async def test_setup_defaults_to_custom_routing_with_selected_model_order(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(setup_api, "async_session_factory", factory)
    monkeypatch.setattr(setup_api, "_write_setup", lambda _data: None)
    monkeypatch.setattr(model_router, "_setup_path", lambda: tmp_path / "setup.json")

    payload = SetupCompletePayload(
        security_incident_acknowledged=True,
        providers=[ProviderSetup(
            provider_type="openai", name="OpenAI", models=["gpt-primary", "gpt-fallback"]
        )],
        primary_model="frontend-provider::gpt-primary",
        fallback_models=["frontend-provider::gpt-fallback"],
    )

    await setup_api.complete_setup(payload)

    async with factory() as session:
        agent = (await session.execute(select(Agent).where(Agent.is_primary.is_(True)))).scalar_one()
        provider = (await session.execute(select(ModelProvider))).scalar_one()
        registry_models = list((await session.execute(select(ModelRegistryEntry))).scalars())
        profile = await session.get(ModelRoutingProfile, agent.model_routing_profile_id)

        assert profile is not None
        assert profile.name == "Custom"
        assert profile.is_default is True
        assert profile.rules == [{
            "task_type": "*",
            "primary_model_id": f"{provider.id}::gpt-primary",
            "fallback_model_ids": [f"{provider.id}::gpt-fallback"],
        }]
        assert {item.model_id for item in registry_models} == {"gpt-primary", "gpt-fallback"}

    await engine.dispose()
