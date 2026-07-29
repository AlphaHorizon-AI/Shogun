"""Add the Bushido Reminder Board durable task and run tables.

Revision ID: 20260730reminders
Revises: 20260729graphretrieval
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260730reminders"
down_revision = "20260729graphretrieval"
branch_labels = None
depends_on = None


def _audit_columns():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(length=255), nullable=True, server_default="system"),
        sa.Column("updated_by", sa.String(length=255), nullable=True, server_default="system"),
    )


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "agent_scheduled_tasks" not in tables:
        op.create_table(
            "agent_scheduled_tasks",
            sa.Column("id", GUID(), primary_key=True, nullable=False),
            sa.Column("tenant_id", sa.String(length=255), nullable=False, server_default="local"),
            sa.Column("user_id", sa.String(length=255), nullable=False, server_default="local_user"),
            sa.Column("agent_id", GUID(), sa.ForeignKey("agents.id"), nullable=True),
            sa.Column("conversation_provider", sa.String(length=50), nullable=False, server_default="web"),
            sa.Column("conversation_id", sa.String(length=255), nullable=True),
            sa.Column("topic_id", sa.String(length=255), nullable=True),
            sa.Column("title", sa.String(length=500), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("schedule_type", sa.String(length=30), nullable=False, server_default="one_time"),
            sa.Column("timezone", sa.String(length=100), nullable=False, server_default="UTC"),
            sa.Column("schedule_time", sa.String(length=10), nullable=True),
            sa.Column("schedule_days", JSONType(), nullable=True),
            sa.Column("interval_minutes", sa.Integer(), nullable=True),
            sa.Column("run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("max_occurrences", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("delivery_channel", sa.String(length=30), nullable=False, server_default="web"),
            sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("snoozed_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("lock_owner", sa.String(length=100), nullable=True),
            sa.Column("lock_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", JSONType(), nullable=False, server_default="{}"),
            *_audit_columns(),
        )
        op.create_index("ix_reminder_due", "agent_scheduled_tasks", ["status", "next_run_at", "lock_until"])
        op.create_index("ix_reminder_scope", "agent_scheduled_tasks", ["tenant_id", "user_id"])

    if "agent_scheduled_task_runs" not in tables:
        op.create_table(
            "agent_scheduled_task_runs",
            sa.Column("id", GUID(), primary_key=True, nullable=False),
            sa.Column(
                "task_id",
                GUID(),
                sa.ForeignKey("agent_scheduled_tasks.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="running"),
            sa.Column("occurrence_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("delivery_result", JSONType(), nullable=False, server_default="{}"),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("correlation_id", sa.String(length=100), nullable=False),
            *_audit_columns(),
        )
        op.create_index("ix_reminder_runs_task", "agent_scheduled_task_runs", ["task_id", "scheduled_for"])


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "agent_scheduled_task_runs" in tables:
        op.drop_table("agent_scheduled_task_runs")
    if "agent_scheduled_tasks" in tables:
        op.drop_table("agent_scheduled_tasks")
