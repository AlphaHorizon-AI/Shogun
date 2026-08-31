"""Add fleet skill assignments and Supermode fleet provenance.

Revision ID: 20260831fleetskills
Revises: 20260831supermode
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260831fleetskills"
down_revision = "20260831supermode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "samurai_profiles" in tables:
        columns = {column["name"] for column in inspector.get_columns("samurai_profiles")}
        if "assigned_skill_ids" not in columns:
            with op.batch_alter_table("samurai_profiles") as batch:
                batch.add_column(
                    sa.Column("assigned_skill_ids", JSONType(), nullable=False, server_default="[]")
                )

    if "mission_agents" in tables:
        columns = {column["name"] for column in inspector.get_columns("mission_agents")}
        additions = (
            ("source_type", sa.Column("source_type", sa.String(30), nullable=False, server_default="spawned")),
            (
                "fleet_agent_id",
                sa.Column(
                    "fleet_agent_id",
                    GUID(),
                    sa.ForeignKey(
                        "agents.id",
                        name="fk_mission_agents_fleet_agent_id_agents",
                        ondelete="SET NULL",
                    ),
                    nullable=True,
                ),
            ),
            ("inherited_skill_ids", sa.Column("inherited_skill_ids", JSONType(), nullable=False, server_default="[]")),
            (
                "inherited_skill_names",
                sa.Column("inherited_skill_names", JSONType(), nullable=False, server_default="[]"),
            ),
            ("agent_routing_reason", sa.Column("agent_routing_reason", sa.String(2000), nullable=True)),
        )
        with op.batch_alter_table("mission_agents") as batch:
            for name, column in additions:
                if name not in columns:
                    batch.add_column(column)

        indexes = {item["name"] for item in sa.inspect(bind).get_indexes("mission_agents")}
        if "ix_mission_agents_fleet_agent_id" not in indexes:
            op.create_index(
                "ix_mission_agents_fleet_agent_id",
                "mission_agents",
                ["fleet_agent_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "mission_agents" in tables:
        indexes = {item["name"] for item in inspector.get_indexes("mission_agents")}
        if "ix_mission_agents_fleet_agent_id" in indexes:
            op.drop_index("ix_mission_agents_fleet_agent_id", table_name="mission_agents")
        columns = {column["name"] for column in inspector.get_columns("mission_agents")}
        with op.batch_alter_table("mission_agents") as batch:
            for name in (
                "agent_routing_reason",
                "inherited_skill_names",
                "inherited_skill_ids",
                "fleet_agent_id",
                "source_type",
            ):
                if name in columns:
                    batch.drop_column(name)

    if "samurai_profiles" in tables:
        columns = {column["name"] for column in inspector.get_columns("samurai_profiles")}
        if "assigned_skill_ids" in columns:
            with op.batch_alter_table("samurai_profiles") as batch:
                batch.drop_column("assigned_skill_ids")
