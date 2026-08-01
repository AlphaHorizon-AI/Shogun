"""Add profile temperatures and deterministic AgentFlow generation controls.

Revision ID: 20260801generation
Revises: 20260730aiobligations
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import JSONType

revision = "20260801generation"
down_revision = "20260730aiobligations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "model_routing_profiles" in tables:
        columns = {column["name"] for column in inspector.get_columns("model_routing_profiles")}
        if "model_settings" not in columns:
            with op.batch_alter_table("model_routing_profiles") as batch:
                batch.add_column(
                    sa.Column("model_settings", JSONType(), nullable=False, server_default="{}")
                )
    if "agent_flows" in tables:
        columns = {column["name"] for column in inspector.get_columns("agent_flows")}
        with op.batch_alter_table("agent_flows") as batch:
            if "seed" not in columns:
                batch.add_column(sa.Column("seed", sa.Integer(), nullable=True))
            if "seed_model_id" not in columns:
                batch.add_column(sa.Column("seed_model_id", sa.String(600), nullable=True))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    if "agent_flows" in tables:
        columns = {column["name"] for column in inspector.get_columns("agent_flows")}
        with op.batch_alter_table("agent_flows") as batch:
            if "seed_model_id" in columns:
                batch.drop_column("seed_model_id")
            if "seed" in columns:
                batch.drop_column("seed")
    if "model_routing_profiles" in tables:
        columns = {column["name"] for column in inspector.get_columns("model_routing_profiles")}
        if "model_settings" in columns:
            with op.batch_alter_table("model_routing_profiles") as batch:
                batch.drop_column("model_settings")
