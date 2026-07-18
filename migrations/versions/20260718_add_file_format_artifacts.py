"""Add the Order 19 file artifact registry.

Revision ID: 20260718fileformats
Revises: 20260718memoryimport
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import JSONType

revision = "20260718fileformats"
down_revision = "20260718memoryimport"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "file_artifacts" in inspector.get_table_names():
        return
    op.create_table(
        "file_artifacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("original_filename", sa.String(500), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("format_id", sa.String(50), nullable=False),
        sa.Column("mime_type", sa.String(255)),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("hash_sha256", sa.String(64), nullable=False),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("detection_confidence", sa.Float(), nullable=False),
        sa.Column("detection_method", sa.String(50), nullable=False),
        sa.Column("permissions", JSONType(), nullable=False),
        sa.Column("capabilities", JSONType(), nullable=False),
        sa.Column("warnings", JSONType(), nullable=False),
        sa.Column("inspection_json", JSONType(), nullable=False),
        sa.Column("last_inspected_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
    )
    op.create_index("ix_file_artifacts_path", "file_artifacts", ["path"], unique=True)
    op.create_index("ix_file_artifacts_format_id", "file_artifacts", ["format_id"])
    op.create_index("ix_file_artifacts_hash_sha256", "file_artifacts", ["hash_sha256"])


def downgrade() -> None:
    op.drop_table("file_artifacts")
