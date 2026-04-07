"""Smoke tests — verify the package can be imported and bootstrapped."""

import pytest


def test_version():
    """Package version is set."""
    import shogun
    assert shogun.__version__ == "0.1.0"


def test_app_factory():
    """FastAPI app factory creates a valid app."""
    from shogun.app import create_app
    app = create_app()
    assert app.title == "Shogun"


def test_openclaw_client_import():
    """OpenClaw client can be imported."""
    from shogun.integrations.openclaw_client import OpenClawClient
    client = OpenClawClient()
    assert client.base_url == "https://www.openclawcollege.com/api"


def test_config_defaults():
    """Config loads with sane defaults."""
    from shogun.config import settings
    assert "sqlite" in settings.database_url
    assert settings.app_env == "development"


def test_all_models_registered():
    """All ORM models are discovered by the base metadata."""
    from shogun.db.base import Base
    import shogun.db.models  # noqa: F401
    tables = Base.metadata.tables
    assert len(tables) >= 20, f"Expected 20+ tables, got {len(tables)}"


@pytest.mark.asyncio
async def test_bootstrap_creates_tables():
    """Bootstrap creates all database tables."""
    from shogun.db.base import Base
    from shogun.db.engine import engine
    import shogun.db.models  # noqa: F401
    from sqlalchemy import inspect

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
        assert len(tables) >= 20

    await engine.dispose()
