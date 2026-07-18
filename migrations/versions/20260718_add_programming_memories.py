"""Add project-scoped programming memory for governed IDE work.

Revision ID: 20260718programmingmemory
Revises: 20260718fileformats
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260718programmingmemory"
down_revision = "20260718fileformats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "programming_memories" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "programming_memories",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("agent_id", GUID(), nullable=False),
        sa.Column("workspace_key", sa.String(64), nullable=False),
        sa.Column("workspace_name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("solution", sa.Text(), nullable=False),
        sa.Column("evidence", sa.Text()),
        sa.Column("validation_status", sa.String(40), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("languages", JSONType(), nullable=False),
        sa.Column("files", JSONType(), nullable=False),
        sa.Column("source_urls", JSONType(), nullable=False),
        sa.Column("tags", JSONType(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("successful_use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
        sa.UniqueConstraint("workspace_key", "content_hash", name="uq_programming_memory_workspace_content"),
    )
    op.create_index("ix_programming_memories_agent_id", "programming_memories", ["agent_id"])
    op.create_index("ix_programming_memories_workspace_key", "programming_memories", ["workspace_key"])
    op.create_index("ix_programming_memories_kind", "programming_memories", ["kind"])
    op.create_index("ix_programming_memories_content_hash", "programming_memories", ["content_hash"])


def downgrade() -> None:
    op.drop_table("programming_memories")
