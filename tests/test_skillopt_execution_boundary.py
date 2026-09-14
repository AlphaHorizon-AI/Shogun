"""Behavior tests verifying that unfinished execution features return actionable unavailable results.

Covers:
- SafeExecutor mode enforcement (only explicit mock/denied modes are implemented)
- SkillOptLabService execute_lab_run returning unavailable without fake usage or fabricated scores
- SkillOptLabService _run_iteration raising NotImplementedError
- RegressionService run_suite returning unavailable without writing fake pass rates to run or suite
- BenchmarkService run_benchmark returning unavailable without writing fictional competence profiles
- BenchmarkService _benchmark_model raising NotImplementedError
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from shogun.db.base import Base
from shogun.db.models.skill import Skill
from shogun.db.models.skillopt import (
    SkillOptBenchmarkRun,
    SkillOptCompetenceProfile,
    SkillOptLabRun,
    SkillOptRegressionCase,
    SkillOptRegressionSuite,
    SkillVersion,
)
from shogun.services.skillopt.benchmark.benchmark_service import BenchmarkService
from shogun.services.skillopt.lab.lab_service import SkillOptLabService
from shogun.services.skillopt.lab.safe_executor import (
    SUPPORTED_EXECUTION_MODES,
    UNSUPPORTED_EXECUTION_MODES,
    SafeExecutor,
)
from shogun.services.skillopt.regression.regression_service import RegressionService

# ── SafeExecutor Mode Enforcement Tests ──────────────────────


def test_safe_executor_rejects_unsupported_live_modes() -> None:
    """SafeExecutor must explicitly reject live and tenant modes rather than silently mocking."""
    for mode in UNSUPPORTED_EXECUTION_MODES:
        with pytest.raises(ValueError, match="unsupported"):
            SafeExecutor(execution_mode=mode)


def test_safe_executor_rejects_unknown_mode() -> None:
    """SafeExecutor must reject arbitrary unknown modes."""
    with pytest.raises(ValueError, match="Unknown execution mode"):
        SafeExecutor(execution_mode="invalid_quantum_mode")


@pytest.mark.parametrize(
    "mode", ["fixture", "replay", "sandbox", "test_tenant", "approved_live_read", "approved_live_write"]
)
def test_unimplemented_modes_never_return_mock_evidence(mode):
    with pytest.raises(ValueError, match="unsupported"):
        SafeExecutor(execution_mode=mode)


def test_safe_executor_accepts_supported_modes() -> None:
    """SafeExecutor allows supported deterministic modes."""
    for mode in SUPPORTED_EXECUTION_MODES:
        executor = SafeExecutor(execution_mode=mode)
        assert executor.execution_mode == mode


def test_safe_executor_denied_mode_execution() -> None:
    """DENIED mode produces denied result without execution."""
    executor = SafeExecutor(execution_mode="denied")
    result = executor.execute_tool_call("test_tool", {"param": 1})
    assert result["status"] == "denied"
    assert result["reason"] == "EXECUTION_MODE_DENIED"


def test_safe_executor_mock_mode_execution() -> None:
    """MOCK mode produces structured mock result."""
    executor = SafeExecutor(execution_mode="mock")
    result = executor.execute_tool_call("test_tool", {"param": 1})
    assert result["status"] == "completed"
    assert result["output"]["mock"] is True


# ── Fixtures for Async Service Tests ─────────────────────────


@pytest.fixture
async def async_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session

    await engine.dispose()


# ── Lab Service Execution Tests ──────────────────────────────


@pytest.mark.asyncio
async def test_lab_execute_returns_unavailable_without_fabrication(async_db: AsyncSession) -> None:
    """execute_lab_run must return status 'unavailable' without writing fake usage or scores."""
    skill_id = uuid.uuid4()
    version_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    skill = Skill(
        id=skill_id,
        name="Local Parser",
        slug="local-parser",
        active_version_id=version_id,
    )
    version = SkillVersion(
        id=version_id,
        skill_id=skill_id,
        version_number=1,
        status="active",
        content_path="/skills/parser.md",
        content_hash="hash1",
        created_at=now,
        updated_at=now,
    )
    run_id = uuid.uuid4()
    run = SkillOptLabRun(
        id=run_id,
        skill_id=skill_id,
        base_version_id=version_id,
        status="pending",
        execution_mode="mock",
        max_iterations=5,
        current_iteration=0,
        total_llm_calls=0,
        total_tool_calls=0,
        total_cost_eur=0.0,
        best_score=None,
    )
    async_db.add_all([skill, version, run])
    await async_db.commit()

    lab_svc = SkillOptLabService(async_db)
    result_run = await lab_svc.execute_lab_run(run_id)

    # Must be marked unavailable
    assert result_run.status == "unavailable"
    assert result_run.result_json.get("error") == "EXECUTION_UNAVAILABLE"

    # Must NOT have fabricated iterations, scores, or resource usage
    assert result_run.current_iteration == 0
    assert result_run.total_llm_calls == 0
    assert result_run.total_tool_calls == 0
    assert result_run.total_cost_eur == 0.0
    assert result_run.best_score is None


@pytest.mark.asyncio
async def test_lab_run_iteration_raises_not_implemented(async_db: AsyncSession) -> None:
    """_run_iteration must reject execution rather than fabricating increasing scores."""
    run = SkillOptLabRun(
        id=uuid.uuid4(),
        skill_id=uuid.uuid4(),
        base_version_id=uuid.uuid4(),
    )
    lab_svc = SkillOptLabService(async_db)
    with pytest.raises(NotImplementedError, match="unavailable|not implemented"):
        await lab_svc._run_iteration(run, 1)


# ── Regression Service Execution Tests ───────────────────────


@pytest.mark.asyncio
async def test_regression_run_suite_returns_unavailable_without_fake_pass_rates(async_db: AsyncSession) -> None:
    """run_suite must return status 'unavailable' without setting pass_rate or suite.last_pass_rate."""
    skill_id = uuid.uuid4()
    suite_id = uuid.uuid4()
    suite = SkillOptRegressionSuite(
        id=suite_id,
        skill_id=skill_id,
        name="Order Form Suite",
        minimum_pass_rate=0.95,
        last_pass_rate=None,
    )
    case = SkillOptRegressionCase(
        id=uuid.uuid4(),
        suite_id=suite_id,
        case_id="tc_01",
        name="Basic Parsing",
        is_enabled=1,
    )
    async_db.add_all([suite, case])
    await async_db.commit()

    reg_svc = RegressionService(async_db)
    run = await reg_svc.run_suite(suite_id)

    assert run.status == "unavailable"
    assert run.pass_rate is None
    assert run.passed_cases == 0
    assert run.failed_cases == 0

    # Suite's last_pass_rate must remain None (no fake pass rate written)
    await async_db.refresh(suite)
    assert suite.last_pass_rate is None


# ── Benchmark Service Execution Tests ────────────────────────


@pytest.mark.asyncio
async def test_benchmark_run_returns_unavailable_without_fake_competence(async_db: AsyncSession) -> None:
    """run_benchmark must return status 'unavailable' without generating random results or competence profiles."""
    skill_id = uuid.uuid4()
    suite_id = uuid.uuid4()
    bench_id = uuid.uuid4()

    bench = SkillOptBenchmarkRun(
        id=bench_id,
        skill_id=skill_id,
        regression_suite_id=suite_id,
        model_ids_json=["gpt-4o", "claude-3-5-sonnet"],
        status="pending",
    )
    async_db.add(bench)
    await async_db.commit()

    bench_svc = BenchmarkService(async_db)
    result = await bench_svc.run_benchmark(bench_id)

    assert result.status == "unavailable"
    assert result.summary_json.get("error") == "EXECUTION_UNAVAILABLE"

    # No competence profiles should have been created
    stmt = sa.select(SkillOptCompetenceProfile).where(SkillOptCompetenceProfile.skill_id == skill_id)
    res = await async_db.execute(stmt)
    assert len(res.scalars().all()) == 0


@pytest.mark.asyncio
async def test_benchmark_model_raises_not_implemented(async_db: AsyncSession) -> None:
    """_benchmark_model must raise NotImplementedError instead of generating random results."""
    bench = SkillOptBenchmarkRun(
        id=uuid.uuid4(),
        skill_id=uuid.uuid4(),
        regression_suite_id=uuid.uuid4(),
    )
    bench_svc = BenchmarkService(async_db)
    with pytest.raises(NotImplementedError, match="unavailable"):
        await bench_svc._benchmark_model(bench, "test-model", 0)
