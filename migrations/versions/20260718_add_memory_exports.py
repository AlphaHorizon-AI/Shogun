"""Add Order 16 portable memory export jobs and items.

Revision ID: 20260718memoryexport
Revises: c57f9d033a44
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import JSONType

revision = "20260718memoryexport"
down_revision = "c57f9d033a44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "memory_export_jobs" not in tables:
        op.create_table(
        "memory_export_jobs",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("requested_by", sa.String(255), nullable=False),
        sa.Column("filters_json", JSONType(), nullable=False),
        sa.Column("counts_json", JSONType(), nullable=False),
        sa.Column("output_dir", sa.String(1000)),
        sa.Column("zip_path", sa.String(1000)),
        sa.Column("error_json", JSONType(), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False),
        )
        op.create_index("ix_memory_export_jobs_status", "memory_export_jobs", ["status"])
    if "memory_export_items" not in tables:
        op.create_table(
        "memory_export_items",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "export_job_id",
            sa.String(64),
            sa.ForeignKey("memory_export_jobs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("output_path", sa.String(1000), nullable=False),
        sa.Column("title", sa.String(500)),
        sa.Column("metadata_json", JSONType(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.Text()),
        )
        op.create_index("ix_memory_export_items_job", "memory_export_items", ["export_job_id"])


def downgrade() -> None:
    op.drop_table("memory_export_items")
    op.drop_table("memory_export_jobs")
