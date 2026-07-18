"""Add Order 17 OpenClaw Markdown memory imports.

Revision ID: 20260718memoryimport
Revises: 20260718memoryexport
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import JSONType

revision = "20260718memoryimport"
down_revision = "20260718memoryexport"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    memory_columns = (
        {column["name"] for column in inspector.get_columns("memory_records")}
        if "memory_records" in tables
        else set()
    )
    for name, column in [
        ("source_system", sa.Column("source_system", sa.String(100))),
        ("source_file", sa.Column("source_file", sa.String(1000))),
        ("source_external_id", sa.Column("source_external_id", sa.String(255))),
        ("import_batch_id", sa.Column("import_batch_id", sa.String(64))),
        ("content_hash", sa.Column("content_hash", sa.String(64))),
        ("tags", sa.Column("tags", JSONType(), nullable=False, server_default="[]")),
    ]:
        if name not in memory_columns:
            op.add_column("memory_records", column)
    inspector = sa.inspect(bind)
    existing_indexes = {
        index["name"] for index in inspector.get_indexes("memory_records")
    }
    for name in ["source_system", "source_external_id", "import_batch_id", "content_hash"]:
        index_name = f"ix_memory_records_{name}"
        if index_name not in existing_indexes:
            op.create_index(index_name, "memory_records", [name])

    if "memory_import_batches" not in tables:
        op.create_table(
        "memory_import_batches",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_name", sa.String(1000)),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("total_files", sa.Integer(), nullable=False),
        sa.Column("valid_count", sa.Integer(), nullable=False),
        sa.Column("imported_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("failed_count", sa.Integer(), nullable=False),
        sa.Column("embedded_count", sa.Integer(), nullable=False),
        sa.Column("warnings_json", JSONType(), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False),
        sa.Column("report_json", JSONType(), nullable=False),
        )
        op.create_index("ix_memory_import_batches_status", "memory_import_batches", ["status"])
    if "memory_import_items" not in tables:
        op.create_table(
        "memory_import_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "batch_id", sa.String(64), sa.ForeignKey("memory_import_batches.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("source_file", sa.String(1000), nullable=False),
        sa.Column("source_external_id", sa.String(255)),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("duplicate_kind", sa.String(40)),
        sa.Column("duplicate_memory_id", sa.String(36)),
        sa.Column("shogun_memory_id", sa.String(36)),
        sa.Column("title", sa.String(500)),
        sa.Column("memory_type", sa.String(50)),
        sa.Column("content_hash", sa.String(64)),
        sa.Column("normalized_json", JSONType(), nullable=False),
        sa.Column("warnings_json", JSONType(), nullable=False),
        sa.Column("error_json", JSONType(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("embedding_error", sa.Text()),
        )
        for name, columns in [
            ("ix_memory_import_items_batch", ["batch_id"]),
            ("ix_memory_import_items_external", ["source_external_id"]),
            ("ix_memory_import_items_status", ["status"]),
            ("ix_memory_import_items_memory", ["shogun_memory_id"]),
            ("ix_memory_import_items_hash", ["content_hash"]),
        ]:
            op.create_index(name, "memory_import_items", columns)


def downgrade() -> None:
    op.drop_table("memory_import_items")
    op.drop_table("memory_import_batches")
    for name in ["content_hash", "import_batch_id", "source_external_id", "source_system"]:
        op.drop_index(f"ix_memory_records_{name}", table_name="memory_records")
    for name in ["tags", "content_hash", "import_batch_id", "source_external_id", "source_file", "source_system"]:
        op.drop_column("memory_records", name)
