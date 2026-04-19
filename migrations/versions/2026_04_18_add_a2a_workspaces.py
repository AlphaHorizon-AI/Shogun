"""add_a2a_workspaces

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(2000), nullable=True),
        sa.Column("topic", sa.String(500), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("scope", sa.String(50), nullable=False, server_default="local"),
        sa.Column("owner_agent_id", sa.String(36), sa.ForeignKey("agents.id"), nullable=True),
        sa.Column("shared_document", sa.Text, nullable=True),
        sa.Column("document_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tags", sa.Text, nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    op.create_table(
        "workspace_peers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("peer_name", sa.String(255), nullable=False, server_default="Unknown Shogun"),
        sa.Column("peer_url", sa.String(1000), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="collaborator"),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shared_secret", sa.String(500), nullable=True),
        sa.Column("peer_meta", sa.Text, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("updated_by", sa.String(255), nullable=True),
    )

    op.create_table(
        "workspace_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("from_agent_id", sa.String(255), nullable=True),
        sa.Column("from_peer_url", sa.String(1000), nullable=True),
        sa.Column("from_name", sa.String(255), nullable=False, server_default="Unknown"),
        sa.Column("message_type", sa.String(50), nullable=False, server_default="update"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("parent_message_id", sa.String(36), sa.ForeignKey("workspace_messages.id"), nullable=True),
        sa.Column("delivery_status", sa.String(50), nullable=False, server_default="local"),
        sa.Column("extra_meta", sa.Text, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workspace_messages")
    op.drop_table("workspace_peers")
    op.drop_table("workspaces")
