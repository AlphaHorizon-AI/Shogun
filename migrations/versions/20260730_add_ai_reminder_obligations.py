"""Extend the Reminder Board with AI operational obligations.

Revision ID: 20260730aiobligations
Revises: 20260730reminders
"""

import sqlalchemy as sa
from alembic import op

revision = "20260730aiobligations"
down_revision = "20260730reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "agent_scheduled_tasks" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("agent_scheduled_tasks")}
    additions = (
        ("origin", sa.Column("origin", sa.String(20), nullable=False, server_default="user")),
        ("item_type", sa.Column("item_type", sa.String(30), nullable=False, server_default="reminder")),
        ("reason", sa.Column("reason", sa.Text(), nullable=True)),
        ("confidence", sa.Column("confidence", sa.Float(), nullable=True)),
        ("expires_at", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True)),
        ("source_message_id", sa.Column("source_message_id", sa.String(255), nullable=True)),
        (
            "requires_confirmation",
            sa.Column("requires_confirmation", sa.Boolean(), nullable=False, server_default=sa.false()),
        ),
    )
    with op.batch_alter_table("agent_scheduled_tasks") as batch:
        for name, column in additions:
            if name not in columns:
                batch.add_column(column)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "agent_scheduled_tasks" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("agent_scheduled_tasks")}
    with op.batch_alter_table("agent_scheduled_tasks") as batch:
        operational_columns = (
            "requires_confirmation", "source_message_id", "expires_at", "confidence",
            "reason", "item_type", "origin",
        )
        for name in operational_columns:
            if name in columns:
                batch.drop_column(name)
