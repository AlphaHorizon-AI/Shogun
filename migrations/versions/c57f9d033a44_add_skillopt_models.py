"""Add SkillOpt models

Revision ID: c57f9d033a44
Revises: 20260717trajectory
Create Date: 2026-07-17 20:25:51.294947

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c57f9d033a44"
down_revision: str | None = "20260717trajectory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the Nexus fields safely to desktop databases already touched by create_all."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "nexus_external_agents" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("nexus_external_agents")}
    if "endpoint_url" not in columns:
        op.add_column(
            "nexus_external_agents",
            sa.Column("endpoint_url", sa.String(length=1000), nullable=True),
        )
    if "direction" not in columns:
        op.add_column(
            "nexus_external_agents",
            sa.Column(
                "direction",
                sa.String(length=20),
                nullable=False,
                server_default="bidirectional",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "nexus_external_agents" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("nexus_external_agents")}
    if "direction" in columns:
        op.drop_column("nexus_external_agents", "direction")
    if "endpoint_url" in columns:
        op.drop_column("nexus_external_agents", "endpoint_url")
