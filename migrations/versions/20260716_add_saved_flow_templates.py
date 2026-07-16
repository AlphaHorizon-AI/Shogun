"""Add reusable AgentFlow and Flow Stack templates.

Revision ID: 20260716tpls
Revises: 20260716orch
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import JSONType

revision = "20260716tpls"
down_revision = "20260716orch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_flows") as batch:
        batch.add_column(sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("template_category", sa.String(100), nullable=True))
        batch.add_column(sa.Column("template_source", sa.String(30), nullable=True))
        batch.add_column(sa.Column("template_config", JSONType(), nullable=False, server_default="{}"))
        batch.create_index("ix_agent_flows_is_template", ["is_template"])
        batch.create_index("ix_agent_flows_template_category", ["template_category"])


def downgrade() -> None:
    with op.batch_alter_table("agent_flows") as batch:
        batch.drop_index("ix_agent_flows_template_category")
        batch.drop_index("ix_agent_flows_is_template")
        batch.drop_column("template_config")
        batch.drop_column("template_source")
        batch.drop_column("template_category")
        batch.drop_column("is_template")
