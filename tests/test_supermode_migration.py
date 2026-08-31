"""Regression coverage for the fleet-routing SQLite migration."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from shogun.db.base import GUID, JSONType

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT / "migrations" / "versions" / "20260831_add_fleet_skill_routing.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("fleet_skill_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("partially_applied", [False, True])
def test_fleet_skill_migration_upgrades_sqlite_with_named_foreign_key(
    tmp_path: Path,
    partially_applied: bool,
) -> None:
    """A retry must work after the first batch completed before a later failure."""
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    metadata = sa.MetaData()
    sa.Table("agents", metadata, sa.Column("id", GUID(), primary_key=True))

    profile_columns = [sa.Column("id", GUID(), primary_key=True)]
    if partially_applied:
        profile_columns.append(
            sa.Column(
                "assigned_skill_ids",
                JSONType(),
                nullable=False,
                server_default="[]",
            )
        )
    sa.Table("samurai_profiles", metadata, *profile_columns)
    sa.Table(
        "mission_agents",
        metadata,
        sa.Column("id", GUID(), primary_key=True),
    )
    metadata.create_all(engine)

    migration = _load_migration()
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()

        inspector = sa.inspect(connection)
        profile_columns = {
            column["name"] for column in inspector.get_columns("samurai_profiles")
        }
        mission_agent_columns = {
            column["name"] for column in inspector.get_columns("mission_agents")
        }
        foreign_keys = inspector.get_foreign_keys("mission_agents")

    assert "assigned_skill_ids" in profile_columns
    assert {
        "source_type",
        "fleet_agent_id",
        "inherited_skill_ids",
        "inherited_skill_names",
        "agent_routing_reason",
    } <= mission_agent_columns
    assert any(
        foreign_key["name"] == "fk_mission_agents_fleet_agent_id_agents"
        and foreign_key["referred_table"] == "agents"
        for foreign_key in foreign_keys
    )

    engine.dispose()
