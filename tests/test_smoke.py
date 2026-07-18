"""Smoke tests — verify the package can be imported and bootstrapped."""

import sqlite3

import pytest


def test_version():
    """Package version is set."""
    import shogun
    assert shogun.__version__ == "1.22.1"


def test_app_factory():
    """FastAPI app factory creates a valid app."""
    from shogun.config import settings
    settings.ensure_directories()
    from shogun.app import create_app
    app = create_app()
    assert app.title == "Shogun"


def test_legacy_sqlite_baseline_detects_unversioned_desktop_schema(tmp_path):
    from shogun.app import _legacy_sqlite_baseline

    database = tmp_path / "legacy.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE agents (id TEXT, openclaw_api_key TEXT)")
        connection.execute("CREATE TABLE chat_messages (id TEXT)")

    assert _legacy_sqlite_baseline(f"sqlite+aiosqlite:///{database.as_posix()}") == "20260706chat"


def test_legacy_sqlite_baseline_leaves_versioned_database_alone(tmp_path):
    from shogun.app import _legacy_sqlite_baseline

    database = tmp_path / "versioned.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE agents (id TEXT, openclaw_api_key TEXT)")
        connection.execute("CREATE TABLE chat_messages (id TEXT)")
        connection.execute("CREATE TABLE alembic_version (version_num TEXT NOT NULL)")
        connection.execute("INSERT INTO alembic_version VALUES ('20260706chat')")

    assert _legacy_sqlite_baseline(f"sqlite+aiosqlite:///{database.as_posix()}") is None


def test_legacy_sqlite_baseline_uses_head_for_bootstrapped_schema(tmp_path):
    from shogun.app import _legacy_sqlite_baseline

    database = tmp_path / "bootstrapped.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE file_artifacts (id TEXT)")

    assert _legacy_sqlite_baseline(f"sqlite+aiosqlite:///{database.as_posix()}") == "20260718fileformats"


@pytest.mark.asyncio
async def test_schema_upgrade_stamps_legacy_database_before_upgrade(tmp_path, monkeypatch):
    from alembic import command

    from shogun.app import _upgrade_database_schema
    from shogun.config import settings

    database = tmp_path / "legacy-upgrade.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE agents (id TEXT, openclaw_api_key TEXT)")
        connection.execute("CREATE TABLE chat_messages (id TEXT)")

    calls = []
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{database.as_posix()}")
    monkeypatch.setattr(command, "stamp", lambda _config, revision: calls.append(("stamp", revision)))
    monkeypatch.setattr(command, "upgrade", lambda _config, revision: calls.append(("upgrade", revision)))

    await _upgrade_database_schema()

    assert calls == [("stamp", "20260706chat"), ("upgrade", "head")]


def test_openclaw_client_import():
    """OpenClaw client can be imported."""
    from shogun.integrations.openclaw_client import OpenClawClient
    client = OpenClawClient()
    assert client.base_url == "https://www.openclawcollege.com/api"


def test_config_defaults():
    """Config loads with sane defaults."""
    from shogun.config import settings
    assert "sqlite" in settings.database_url
    assert settings.app_env in ["development", "production"]


def test_all_models_registered():
    """All ORM models are discovered by the base metadata."""
    import shogun.db.models  # noqa: F401
    from shogun.db.base import Base
    tables = Base.metadata.tables
    assert len(tables) >= 20, f"Expected 20+ tables, got {len(tables)}"


@pytest.mark.asyncio
async def test_bootstrap_creates_tables():
    """Bootstrap creates all database tables."""
    from shogun.config import settings
    settings.ensure_directories()
    from sqlalchemy import inspect

    import shogun.db.models  # noqa: F401
    from shogun.db.base import Base
    from shogun.db.engine import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
        assert len(tables) >= 20

    await engine.dispose()
