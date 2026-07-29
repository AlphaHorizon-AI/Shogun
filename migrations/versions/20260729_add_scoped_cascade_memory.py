"""Add Phase 1 scoped cascade memory foundations.

Revision ID: 20260729cascade
Revises: 20260728stackoutput
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260729cascade"
down_revision = "20260728stackoutput"
branch_labels = None
depends_on = None


SCOPE_COLUMNS = (
    sa.Column("tenant_id", sa.String(length=255), nullable=False, server_default="local"),
    sa.Column("user_id", sa.String(length=255), nullable=True),
    sa.Column("team_id", sa.String(length=255), nullable=True),
    sa.Column("workspace_id", sa.String(length=255), nullable=True),
    sa.Column("project_id", sa.String(length=255), nullable=True),
    sa.Column("workflow_id", sa.String(length=255), nullable=True),
    sa.Column("conversation_provider", sa.String(length=50), nullable=True),
    sa.Column("conversation_id", sa.String(length=255), nullable=True),
    sa.Column("topic_id", sa.String(length=255), nullable=True),
    sa.Column("sensitivity", sa.String(length=30), nullable=False, server_default="internal"),
    sa.Column("scope_status", sa.String(length=30), nullable=False, server_default="agent_private"),
    sa.Column("policy_version", sa.String(length=100), nullable=True),
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "memory_records" in tables:
        existing = {column["name"] for column in inspector.get_columns("memory_records")}
        for column in SCOPE_COLUMNS:
            if column.name not in existing:
                op.add_column("memory_records", column)

        existing_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("memory_records")}
        indexes = {
            "ix_memory_records_tenant_agent": ["tenant_id", "agent_id"],
            "ix_memory_records_topic_scope": ["tenant_id", "conversation_id", "topic_id"],
            "ix_memory_records_project_scope": ["tenant_id", "workspace_id", "project_id"],
        }
        for name, columns in indexes.items():
            if name not in existing_indexes:
                op.create_index(name, "memory_records", columns, unique=False)

    if "memory_retrieval_runs" not in tables:
        op.create_table(
            "memory_retrieval_runs",
            sa.Column("id", GUID(), primary_key=True, nullable=False),
            sa.Column("correlation_id", sa.String(length=64), nullable=False),
            sa.Column("query_hash", sa.String(length=64), nullable=False),
            sa.Column("mode", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="started"),
            sa.Column("agent_id", GUID(), nullable=True),
            sa.Column("scope_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("plan_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("stages_json", JSONType(), nullable=False, server_default="[]"),
            sa.Column("result_memory_ids", JSONType(), nullable=False, server_default="[]"),
            sa.Column("excluded_json", JSONType(), nullable=False, server_default="[]"),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index("ix_memory_retrieval_runs_correlation_id", "memory_retrieval_runs", ["correlation_id"], unique=True)
        op.create_index("ix_memory_retrieval_runs_agent_id", "memory_retrieval_runs", ["agent_id"], unique=False)
        op.create_index("ix_memory_retrieval_runs_created_at", "memory_retrieval_runs", ["created_at"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "memory_retrieval_runs" in tables:
        op.drop_table("memory_retrieval_runs")
    if "memory_records" not in tables:
        return
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("memory_records")}
    for name in (
        "ix_memory_records_project_scope",
        "ix_memory_records_topic_scope",
        "ix_memory_records_tenant_agent",
    ):
        if name in indexes:
            op.drop_index(name, table_name="memory_records")
    existing = {column["name"] for column in sa.inspect(bind).get_columns("memory_records")}
    for column in reversed(SCOPE_COLUMNS):
        if column.name in existing:
            op.drop_column("memory_records", column.name)
