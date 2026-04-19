"""add openclaw_api_key to agents

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-04-18

"""
from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "agents",
        sa.Column("openclaw_api_key", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agents", "openclaw_api_key")
