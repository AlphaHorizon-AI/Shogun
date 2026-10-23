"""Local daemon discovery must preserve existing operator configuration."""

import importlib
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.api.system import _sync_ollama_providers
from shogun.db.models.model_provider import ModelProvider


@pytest.mark.asyncio
@pytest.mark.parametrize("discovered", [[], ["current:latest"]])
async def test_discovery_keeps_unreported_provider_and_custom_configuration(monkeypatch, discovered):
    database = importlib.import_module("shogun.db.engine")

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(database, "async_session_factory", sessions)
    async with engine.begin() as connection:
        await connection.run_sync(ModelProvider.__table__.create)

    provider_id = uuid.uuid4()
    configuration = {"models": ["saved:latest"], "operator_option": "retain"}
    async with sessions() as session:
        session.add(ModelProvider(
            id=provider_id, provider_type="ollama", name="saved:latest", slug="saved-latest",
            base_url="http://localhost:11434", auth_type="none", is_local=True,
            status="connected", health_status="healthy", config=configuration,
        ))
        await session.commit()

    try:
        await _sync_ollama_providers(discovered, "http://localhost:11434")
        async with sessions() as session:
            saved = await session.get(ModelProvider, provider_id)
            assert saved is not None
            assert saved.config == configuration
            providers = list((await session.scalars(select(ModelProvider))).all())
            assert {provider.name for provider in providers} == {"saved:latest", *discovered}
    finally:
        await engine.dispose()
