"""Add Phase 3 graph retrieval context packs.

Revision ID: 20260729graphretrieval
Revises: 20260729memorygraph
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260729graphretrieval"
down_revision = "20260729memorygraph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "memory_context_packs" in tables:
        return
    op.create_table(
        "memory_context_packs",
        sa.Column("id", GUID(), primary_key=True, nullable=False),
        sa.Column("correlation_id", sa.String(length=64), nullable=False),
        sa.Column("query_hash", sa.String(length=64), nullable=False),
        sa.Column("agent_id", GUID(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="ready"),
        sa.Column("scope_json", JSONType(), nullable=False, server_default="{}"),
        sa.Column("content_json", JSONType(), nullable=False, server_default="{}"),
        sa.Column("included_memory_ids", JSONType(), nullable=False, server_default="[]"),
        sa.Column("graph_expanded_memory_ids", JSONType(), nullable=False, server_default="[]"),
        sa.Column("excluded_json", JSONType(), nullable=False, server_default="[]"),
        sa.Column("warnings_json", JSONType(), nullable=False, server_default="[]"),
        sa.Column("policy_notes", JSONType(), nullable=False, server_default="[]"),
        sa.Column("token_estimate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_memory_context_packs_correlation_id",
        "memory_context_packs",
        ["correlation_id"],
        unique=True,
    )
    op.create_index(
        "ix_memory_context_packs_agent_id", "memory_context_packs", ["agent_id"], unique=False
    )
    op.create_index(
        "ix_memory_context_packs_created_at", "memory_context_packs", ["created_at"], unique=False
    )


def downgrade() -> None:
    if "memory_context_packs" in set(sa.inspect(op.get_bind()).get_table_names()):
        op.drop_table("memory_context_packs")
