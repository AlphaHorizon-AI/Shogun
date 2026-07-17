from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.db.base import Base
from shogun.db.models.model_provider import ModelProvider
from shogun.db.models.model_router import ModelRegistryEntry
from shogun.schemas.model_router import ModelRouteRequest, ModelUsageCreate
from shogun.services.model_router import (
    ComplexityScoringService,
    ModelRoutingService,
    ModelUsageLogger,
    NoEligibleModelError,
    TaskClassifierService,
    infer_tiers,
)


@pytest.fixture
async def routing_session(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    from shogun.services import model_router

    monkeypatch.setattr(model_router, "_setup_path", lambda: tmp_path / "setup.json")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


async def _model(
    session, model_id: str, *, quality: int, cost: int, local: bool = False, capabilities: dict | None = None
) -> ModelRegistryEntry:
    provider = ModelProvider(
        id=uuid.uuid4(),
        provider_type="ollama" if local else "openrouter",
        name=model_id,
        slug=f"provider-{uuid.uuid4().hex}",
        base_url="http://localhost:11434" if local else "https://example.test/v1",
        is_local=local,
        status="connected",
        config={"model_id": model_id},
    )
    entry = ModelRegistryEntry(
        model_id=model_id,
        display_name=model_id,
        provider_id=provider.id,
        provider=provider.provider_type,
        connection_type="local" if local else "api",
        enabled=True,
        capabilities=capabilities or {"chat": True},
        quality_tier=quality,
        cost_tier=cost,
        latency_tier=quality,
        context_window=128000,
        max_output_tokens=4096,
        local=local,
        role_tags=[],
        config_json={},
    )
    session.add_all([provider, entry])
    await session.flush()
    return entry


@pytest.mark.asyncio
async def test_five_default_profiles_are_seeded_with_balanced_active(routing_session):
    service = ModelRoutingService(routing_session)
    profiles = await service.ensure_defaults()
    assert {item.name for item in profiles} >= {"Ultra Economy", "Economy", "Balanced", "High Capability", "Premium"}
    assert (await service.active_profile()).name == "Balanced"


def test_classifier_and_complexity_are_deterministic():
    request = ModelRouteRequest(prompt="Implement a multi-file refactor and run tests", file_count=7, tool_count=3)
    task = TaskClassifierService.classify(request)
    assert task == "coding_edit"
    assert ComplexityScoringService.score(request, task) == 5
    assert infer_tiers("z-ai/glm-5.2", False) == (4, 3, 3)


@pytest.mark.asyncio
async def test_balanced_coding_routes_to_sufficient_coding_model(routing_session):
    await _model(
        routing_session,
        "glm-4.7-flash",
        quality=2,
        cost=1,
        capabilities={"chat": True, "coding": True, "tool_use": True},
    )
    await _model(
        routing_session,
        "generic-coding-pro",
        quality=4,
        cost=3,
        capabilities={"chat": True, "coding": True, "reasoning": True, "tool_use": True},
    )
    strong = await _model(
        routing_session,
        "glm-5.2",
        quality=5,
        cost=4,
        capabilities={"chat": True, "coding": True, "reasoning": True, "tool_use": True},
    )
    result = await ModelRoutingService(routing_session).route(
        ModelRouteRequest(
            prompt="Refactor the backend",
            task_type="coding_edit",
            required_capabilities=["coding", "tool_use"],
            profile_override="balanced",
        )
    )
    assert result.selected.id == strong.id
    assert result.decision is not None
    assert result.payload["complexity_score"] == 4


@pytest.mark.asyncio
async def test_vision_hard_requirement_never_selects_text_model(routing_session):
    await _model(
        routing_session, "glm-5.2", quality=5, cost=4, capabilities={"chat": True, "reasoning": True, "vision": False}
    )
    vision = await _model(
        routing_session, "gemma3:12b", quality=3, cost=1, local=True, capabilities={"chat": True, "vision": True}
    )
    await _model(
        routing_session,
        "cloud-vision-pro",
        quality=5,
        cost=4,
        capabilities={"chat": True, "vision": True, "long_context": True},
    )
    result = await ModelRoutingService(routing_session).route(
        ModelRouteRequest(
            prompt="What is in this screenshot?",
            task_type="visual_understanding",
            context_size_estimate=250_000,
            local_only=True,
        )
    )
    assert result.selected.id == vision.id
    assert result.payload["requires_vision"] is True


@pytest.mark.asyncio
async def test_local_only_and_no_eligible_model_are_enforced(routing_session):
    await _model(routing_session, "cloud-text", quality=5, cost=4, capabilities={"chat": True})
    local = await _model(routing_session, "local-text", quality=2, cost=1, local=True, capabilities={"chat": True})
    result = await ModelRoutingService(routing_session).route(ModelRouteRequest(prompt="Hello", local_only=True))
    assert result.selected.id == local.id
    with pytest.raises(NoEligibleModelError, match="vision"):
        await ModelRoutingService(routing_session).route(
            ModelRouteRequest(
                prompt="Inspect image",
                task_type="visual_understanding",
                local_only=True,
            )
        )


@pytest.mark.asyncio
async def test_escalation_excludes_failed_model_and_usage_is_logged(routing_session):
    failed = await _model(routing_session, "glm-flash", quality=2, cost=1, capabilities={"chat": True})
    strong = await _model(routing_session, "glm-5.2", quality=5, cost=4, capabilities={"chat": True})
    result = await ModelRoutingService(routing_session).route(
        ModelRouteRequest(
            prompt="Retry after failed verification",
            task_type="complex_reasoning",
            verification_status="failed",
            escalation_level=1,
            exclude_model_ids=[failed.model_id],
        )
    )
    assert result.selected.id == strong.id
    usage = await ModelUsageLogger(routing_session).log(
        ModelUsageCreate(
            routing_decision_id=result.decision.id,
            model_id=strong.model_id,
            provider=strong.provider,
            input_tokens=100,
            output_tokens=25,
            latency_ms=900,
            success=True,
        )
    )
    assert usage.routing_decision_id == result.decision.id
    summary = await ModelUsageLogger(routing_session).summary()
    assert summary["input_tokens"] == 100 and summary["events"] == 1


@pytest.mark.asyncio
async def test_daily_budget_warn_and_block_policies(routing_session, tmp_path):
    await _model(routing_session, "glm-4.7-flash", quality=2, cost=1, capabilities={"chat": True})
    await ModelUsageLogger(routing_session).log(
        ModelUsageCreate(
            model_id="glm-4.7-flash",
            provider="openrouter",
            estimated_cost=2.0,
        )
    )
    setup_path = tmp_path / "setup.json"
    setup_path.write_text(
        json.dumps(
            {
                "model_routing": {
                    "daily_budget": {"enabled": True, "amount": 1, "currency": "USD", "on_exceed": "warn"},
                }
            }
        ),
        encoding="utf-8",
    )
    warning = await ModelRoutingService(routing_session).route(ModelRouteRequest(prompt="Hello"))
    assert "Daily budget reached" in warning.payload["metadata"]["budget_warning"]

    setup_path.write_text(
        json.dumps(
            {
                "model_routing": {
                    "daily_budget": {"enabled": True, "amount": 1, "currency": "USD", "on_exceed": "block"},
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(NoEligibleModelError, match="Daily model budget reached"):
        await ModelRoutingService(routing_session).route(ModelRouteRequest(prompt="Hello"))
