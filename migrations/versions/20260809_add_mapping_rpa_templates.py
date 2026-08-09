"""Add reusable Mapping / RPA templates.

Revision ID: 20260809mappingrpa
Revises: 20260801generation
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260809mappingrpa"
down_revision = "20260801generation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "mapping_templates" in set(inspector.get_table_names()):
        return
    op.create_table(
        "mapping_templates",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("scope", sa.String(20), nullable=False, server_default="private"),
        sa.Column("owner_id", sa.String(255), nullable=False, server_default="system"),
        sa.Column("team_id", sa.String(255), nullable=True),
        sa.Column("config", JSONType(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mapping_templates_name", "mapping_templates", ["name"])
    op.create_index("ix_mapping_templates_scope", "mapping_templates", ["scope"])
    op.create_index("ix_mapping_templates_owner_id", "mapping_templates", ["owner_id"])
    op.create_index("ix_mapping_templates_team_id", "mapping_templates", ["team_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "mapping_templates" in set(inspector.get_table_names()):
        op.drop_table("mapping_templates")
