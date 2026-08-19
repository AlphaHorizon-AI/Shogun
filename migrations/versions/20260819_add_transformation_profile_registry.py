"""Add governed transformation profile registry and protected built-in skills.

Revision ID: 20260819transprofiles
Revises: 20260809mappingrpa
"""

import sqlalchemy as sa
from alembic import op

from shogun.db.base import GUID, JSONType

revision = "20260819transprofiles"
down_revision = "20260809mappingrpa"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "skills" in tables:
        columns = {column["name"] for column in inspector.get_columns("skills")}
        with op.batch_alter_table("skills") as batch:
            if "is_builtin" not in columns:
                batch.add_column(
                    sa.Column(
                        "is_builtin",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.false(),
                    )
                )
            if "is_protected" not in columns:
                batch.add_column(
                    sa.Column(
                        "is_protected",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.false(),
                    )
                )

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "transformation_adapters" not in tables:
        op.create_table(
            "transformation_adapters",
            sa.Column("adapter_id", sa.String(255), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="planned"),
            sa.Column("implementation", sa.String(500), nullable=True),
            sa.Column("capabilities", JSONType(), nullable=False, server_default="[]"),
            sa.Column("metadata_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True),
            sa.Column("updated_by", sa.String(255), nullable=True),
            sa.PrimaryKeyConstraint("adapter_id"),
        )
        op.create_index(
            "ix_transformation_adapters_status",
            "transformation_adapters",
            ["status"],
        )

    if "transformation_profiles" not in tables:
        op.create_table(
            "transformation_profiles",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("profile_key", sa.String(255), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("platform", sa.String(100), nullable=False, server_default="generic"),
            sa.Column("domain", sa.String(100), nullable=False, server_default="document"),
            sa.Column("lifecycle_status", sa.String(30), nullable=False, server_default="candidate"),
            sa.Column("protected", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("bundled", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("active_version_id", GUID(), nullable=True),
            sa.Column("source_resource", sa.String(500), nullable=True),
            sa.Column("metadata_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True),
            sa.Column("updated_by", sa.String(255), nullable=True),
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("profile_key", name="uq_transformation_profile_key"),
        )
        op.create_index(
            "ix_transformation_profiles_profile_key",
            "transformation_profiles",
            ["profile_key"],
        )
        op.create_index(
            "ix_transformation_profiles_platform",
            "transformation_profiles",
            ["platform"],
        )
        op.create_index(
            "ix_transformation_profiles_domain",
            "transformation_profiles",
            ["domain"],
        )
        op.create_index(
            "ix_transformation_profiles_lifecycle_status",
            "transformation_profiles",
            ["lifecycle_status"],
        )
        op.create_index(
            "ix_transformation_profiles_protected",
            "transformation_profiles",
            ["protected"],
        )
        op.create_index(
            "ix_transformation_profiles_bundled",
            "transformation_profiles",
            ["bundled"],
        )
        op.create_index(
            "ix_transformation_profiles_active_version_id",
            "transformation_profiles",
            ["active_version_id"],
        )
        op.create_index(
            "ix_transformation_profile_platform_domain",
            "transformation_profiles",
            ["platform", "domain"],
        )

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "transformation_profile_versions" not in tables:
        op.create_table(
            "transformation_profile_versions",
            sa.Column("id", GUID(), nullable=False),
            sa.Column("profile_id", GUID(), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="candidate"),
            sa.Column("adapter_id", sa.String(255), nullable=False),
            sa.Column("required_adapter_status", sa.String(30), nullable=False, server_default="available"),
            sa.Column("origin", sa.String(30), nullable=False, server_default="skillopt"),
            sa.Column("content_hash", sa.String(64), nullable=False),
            sa.Column("definition", JSONType(), nullable=False, server_default="{}"),
            sa.Column("parent_version_id", GUID(), nullable=True),
            sa.Column("validation_score", sa.Float(), nullable=True),
            sa.Column("validation_report", JSONType(), nullable=False, server_default="{}"),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", JSONType(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.String(255), nullable=True),
            sa.Column("updated_by", sa.String(255), nullable=True),
            sa.ForeignKeyConstraint(
                ["profile_id"],
                ["transformation_profiles.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["adapter_id"],
                ["transformation_adapters.adapter_id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["parent_version_id"],
                ["transformation_profile_versions.id"],
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "profile_id",
                "version_number",
                name="uq_transformation_profile_version_number",
            ),
        )
        op.create_index(
            "ix_transformation_profile_versions_profile_id",
            "transformation_profile_versions",
            ["profile_id"],
        )
        op.create_index(
            "ix_transformation_profile_versions_status",
            "transformation_profile_versions",
            ["status"],
        )
        op.create_index(
            "ix_transformation_profile_versions_adapter_id",
            "transformation_profile_versions",
            ["adapter_id"],
        )
        op.create_index(
            "ix_transformation_profile_versions_origin",
            "transformation_profile_versions",
            ["origin"],
        )
        op.create_index(
            "ix_transformation_profile_version_status",
            "transformation_profile_versions",
            ["profile_id", "status"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "transformation_profile_versions" in tables:
        op.drop_table("transformation_profile_versions")
    if "transformation_profiles" in tables:
        op.drop_table("transformation_profiles")
    if "transformation_adapters" in tables:
        op.drop_table("transformation_adapters")

    inspector = sa.inspect(bind)
    if "skills" in set(inspector.get_table_names()):
        columns = {column["name"] for column in inspector.get_columns("skills")}
        with op.batch_alter_table("skills") as batch:
            if "is_protected" in columns:
                batch.drop_column("is_protected")
            if "is_builtin" in columns:
                batch.drop_column("is_builtin")
