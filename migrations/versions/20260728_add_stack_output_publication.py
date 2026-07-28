"""Add Flow Stack handover publication controls.

Revision ID: 20260728stackoutput
Revises: 20260718programmingmemory
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import JSONType

revision = "20260728stackoutput"
down_revision = "20260718programmingmemory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "stack_runs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("stack_runs")}
    if "output_publication" not in columns:
        op.add_column(
            "stack_runs",
            sa.Column("output_publication", sa.String(length=30), nullable=False, server_default="summary_and_final"),
        )
    if "published_output" not in columns:
        op.add_column(
            "stack_runs",
            sa.Column("published_output", JSONType(), nullable=False, server_default="{}"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "stack_runs" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("stack_runs")}
    if "published_output" in columns:
        op.drop_column("stack_runs", "published_output")
    if "output_publication" in columns:
        op.drop_column("stack_runs", "output_publication")
