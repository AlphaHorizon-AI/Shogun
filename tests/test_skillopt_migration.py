"""Synthetic upgrade preservation test for the SkillOpt Lab Alembic migration."""

from __future__ import annotations

import importlib.util
import uuid
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

from shogun.db.base import GUID, JSONType

ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = ROOT / "migrations" / "versions" / "20260914_add_skillopt_lab_tables.py"


def _load_migration():
    spec = importlib.util.spec_from_file_location("skillopt_lab_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_skillopt_lab_migration_preserves_preexisting_data_and_is_idempotent(
    tmp_path: Path,
) -> None:
    """Verify pre-migration data preservation, column additions, backfills, and idempotency."""
    db_path = tmp_path / "skillopt_migration.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")
    metadata = sa.MetaData()

    # Pre-migration tables
    skills_table = sa.Table(
        "skills",
        metadata,
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
    )

    skill_versions_table = sa.Table(
        "skill_versions",
        metadata,
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("content_path", sa.String(500), nullable=False),
        sa.Column("content_hash", sa.String(255), nullable=False),
        sa.Column("parent_version_id", GUID(), nullable=True),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column("validation_score", sa.Float(), nullable=True),
        sa.Column("metadata_json", JSONType(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    training_runs_table = sa.Table(
        "skillopt_training_runs",
        metadata,
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("base_version_id", GUID(), sa.ForeignKey("skill_versions.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    candidates_table = sa.Table(
        "skillopt_candidates",
        metadata,
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("training_run_id", GUID(), sa.ForeignKey("skillopt_training_runs.id"), nullable=False),
        sa.Column("skill_id", GUID(), sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("base_version_id", GUID(), sa.ForeignKey("skill_versions.id"), nullable=False),
        sa.Column("candidate_content_path", sa.String(500), nullable=False),
        sa.Column("candidate_diff_path", sa.String(500), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("metadata_json", JSONType(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    metadata.create_all(engine)

    # Seed preexisting records
    skill_id = uuid.uuid4()
    ver_id = uuid.uuid4()
    tr_id = uuid.uuid4()
    cand_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with engine.begin() as conn:
        conn.execute(
            skills_table.insert().values(
                id=str(skill_id),
                name="Legacy Skill",
                slug="legacy-skill",
            )
        )
        conn.execute(
            skill_versions_table.insert().values(
                id=str(ver_id),
                skill_id=str(skill_id),
                version_number=1,
                status="active",
                content_path="/skills/legacy/1.md",
                content_hash="abc123hash",
                parent_version_id=None,
                created_by="system",
                validation_score=0.98,
                metadata_json="{}",
                created_at=now,
                updated_at=now,
            )
        )
        conn.execute(
            training_runs_table.insert().values(
                id=str(tr_id),
                skill_id=str(skill_id),
                base_version_id=str(ver_id),
                status="completed",
                created_at=now,
                updated_at=now,
            )
        )
        conn.execute(
            candidates_table.insert().values(
                id=str(cand_id),
                training_run_id=str(tr_id),
                skill_id=str(skill_id),
                base_version_id=str(ver_id),
                candidate_content_path="/skills/legacy/cand.md",
                candidate_diff_path="/skills/legacy/cand.diff",
                status="validated",
                metadata_json="{}",
                created_at=now,
                updated_at=now,
            )
        )

    # Load and execute migration twice (idempotency check)
    migration = _load_migration()
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        migration.upgrade()  # Second run must be safe and idempotent

        inspector = sa.inspect(connection)
        tables = set(inspector.get_table_names())

        ver_columns = {c["name"] for c in inspector.get_columns("skill_versions")}
        cand_columns = {c["name"] for c in inspector.get_columns("skillopt_candidates")}

    # Verify existing tables gained the extension columns
    assert "scope" in ver_columns
    assert "quarantine_status" in ver_columns
    assert "approval_policy" in ver_columns
    assert "tool_schema_hashes_json" in ver_columns

    assert "textual_gradient_json" in cand_columns
    assert "iteration_number" in cand_columns
    assert "tool_schema_hashes_json" in cand_columns

    # Verify all 8 new Lab tables exist
    assert {
        "skillopt_lab_runs",
        "skillopt_regression_suites",
        "skillopt_regression_cases",
        "skillopt_regression_runs",
        "skillopt_benchmark_runs",
        "skillopt_benchmark_results",
        "skillopt_competence_profiles",
        "skillopt_tool_schema_versions",
    } <= tables

    # Verify preexisting data preservation and column backfills
    with engine.begin() as conn:
        v_row = (
            conn.execute(
                sa.text(
                    "SELECT version_number, content_hash, scope, approval_policy, tool_schema_hashes_json "
                    f"FROM skill_versions WHERE id = '{ver_id}'"
                )
            )
            .mappings()
            .one()
        )
        assert v_row["version_number"] == 1
        assert v_row["content_hash"] == "abc123hash"
        assert v_row["scope"] == "local"
        assert v_row["approval_policy"] == "require_local_admin"

        c_row = (
            conn.execute(
                sa.text(
                    "SELECT status, candidate_content_path, iteration_number, textual_gradient_json "
                    f"FROM skillopt_candidates WHERE id = '{cand_id}'"
                )
            )
            .mappings()
            .one()
        )
        assert c_row["status"] == "validated"
        assert c_row["candidate_content_path"] == "/skills/legacy/cand.md"
        assert c_row["iteration_number"] == 1

        # Test inserting into new lab table
        lab_run_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO skillopt_lab_runs (id, skill_id, base_version_id, status, execution_mode, max_iterations, "
                "max_llm_calls, max_tool_calls, max_runtime_seconds, max_cost_eur, current_iteration, total_llm_calls, "
                "total_tool_calls, total_cost_eur, result_json, config_json, created_at, updated_at) "
                f"VALUES ('{lab_run_id}', '{skill_id}', '{ver_id}', 'pending', 'mock', "
                f"10, 40, 100, 900, 5.0, 0, 0, 0, 0.0, '{{}}', '{{}}', '{now.isoformat()}', '{now.isoformat()}')"
            )
        )
        lab_row = (
            conn.execute(sa.text(f"SELECT status, execution_mode FROM skillopt_lab_runs WHERE id = '{lab_run_id}'"))
            .mappings()
            .one()
        )
        assert lab_row["status"] == "pending"
        assert lab_row["execution_mode"] == "mock"

    engine.dispose()
