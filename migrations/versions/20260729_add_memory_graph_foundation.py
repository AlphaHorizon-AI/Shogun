"""Add the Phase 2 Kiroku MemoryGraph foundation.

Revision ID: 20260729memorygraph
Revises: 20260729cascade
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260729memorygraph"
down_revision = "20260729cascade"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "memory_graph_nodes" not in tables:
        op.create_table(
            "memory_graph_nodes",
            sa.Column("id", GUID(), primary_key=True, nullable=False),
            sa.Column("canonical_key", sa.String(length=700), nullable=False),
            sa.Column("node_type", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=500), nullable=False),
            sa.Column("display_name", sa.String(length=500), nullable=True),
            sa.Column("payload_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("scope_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("tenant_id", sa.String(length=255), nullable=False, server_default="local"),
            sa.Column("user_id", sa.String(length=255), nullable=True),
            sa.Column("team_id", sa.String(length=255), nullable=True),
            sa.Column("workspace_id", sa.String(length=255), nullable=True),
            sa.Column("project_id", sa.String(length=255), nullable=True),
            sa.Column("agent_id", GUID(), nullable=True),
            sa.Column("topic_id", sa.String(length=255), nullable=True),
            sa.Column("sensitivity", sa.String(length=30), nullable=False, server_default="internal"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("source_memory_id", GUID(), nullable=True),
            sa.Column("qdrant_point_id", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("updated_by", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["source_memory_id"], ["memory_records.id"], ondelete="SET NULL"),
            sa.UniqueConstraint("canonical_key", name="uq_memory_graph_nodes_canonical_key"),
            sa.UniqueConstraint("source_memory_id", name="uq_memory_graph_nodes_source_memory_id"),
        )
        op.create_index(
            "ix_memory_graph_nodes_scope",
            "memory_graph_nodes",
            ["tenant_id", "workspace_id", "project_id"],
        )
        op.create_index(
            "ix_memory_graph_nodes_type_status", "memory_graph_nodes", ["node_type", "status"]
        )

    if "memory_graph_edges" not in tables:
        op.create_table(
            "memory_graph_edges",
            sa.Column("id", GUID(), primary_key=True, nullable=False),
            sa.Column("from_node_id", GUID(), nullable=False),
            sa.Column("to_node_id", GUID(), nullable=False),
            sa.Column("relationship_type", sa.String(length=60), nullable=False),
            sa.Column("weight", sa.Float(), nullable=False, server_default="1"),
            sa.Column("confidence", sa.Float(), nullable=False, server_default="1"),
            sa.Column("source_memory_id", GUID(), nullable=True),
            sa.Column("payload_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("updated_by", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["from_node_id"], ["memory_graph_nodes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["to_node_id"], ["memory_graph_nodes.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["source_memory_id"], ["memory_records.id"], ondelete="SET NULL"),
            sa.UniqueConstraint(
                "from_node_id", "to_node_id", "relationship_type", name="uq_memory_graph_edges_relation"
            ),
        )
        op.create_index(
            "ix_memory_graph_edges_from_type", "memory_graph_edges", ["from_node_id", "relationship_type"]
        )
        op.create_index(
            "ix_memory_graph_edges_to_type", "memory_graph_edges", ["to_node_id", "relationship_type"]
        )

    if "memory_graph_conflicts" not in tables:
        op.create_table(
            "memory_graph_conflicts",
            sa.Column("id", GUID(), primary_key=True, nullable=False),
            sa.Column("memory_id_a", GUID(), nullable=False),
            sa.Column("memory_id_b", GUID(), nullable=False),
            sa.Column("conflict_type", sa.String(length=50), nullable=False, server_default="contradiction"),
            sa.Column("resolution_status", sa.String(length=30), nullable=False, server_default="needs_review"),
            sa.Column("resolved_by", sa.String(length=255), nullable=True),
            sa.Column("resolution_note", sa.Text(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(length=255), nullable=True),
            sa.Column("updated_by", sa.String(length=255), nullable=True),
            sa.ForeignKeyConstraint(["memory_id_a"], ["memory_records.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["memory_id_b"], ["memory_records.id"], ondelete="CASCADE"),
        )
        op.create_index(
            "ix_memory_graph_conflicts_status",
            "memory_graph_conflicts",
            ["resolution_status", "created_at"],
        )
        op.create_index(
            "ix_memory_graph_conflicts_memories",
            "memory_graph_conflicts",
            ["memory_id_a", "memory_id_b"],
        )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    for table in ("memory_graph_conflicts", "memory_graph_edges", "memory_graph_nodes"):
        if table in tables:
            op.drop_table(table)
