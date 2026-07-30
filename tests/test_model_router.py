from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.api.model_router import set_active_profile
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.model_definition import ModelDefinition
from shogun.db.models.model_provider import ModelProvider
from shogun.db.models.model_router import ModelRegistryEntry
from shogun.db.models.model_routing import ModelRoutingProfile
from shogun.engine.flow_engine import _resolve_model_target
from shogun.schemas.model_router import ActiveProfileRequest, ModelRouteRequest, ModelUsageCreate
from shogun.services.model_router import (
    ComplexityScoringService,
    ModelRegistryService,
    ModelRoutingService,
    ModelUsageLogger,
    NoEligibleModelError,
    TaskClassifierService,
    infer_tiers,
    is_concrete_model_id,
    legacy_provider_name_model_id,
)
from shogun.services.model_service import ModelRoutingProfileService


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
async def test_registry_sync_uses_explicit_models_even_when_definitions_exist(routing_session):
    provider = ModelProvider(
        provider_type="openrouter",
        name="Primary OpenRouter",
        slug="primary-openrouter",
        base_url="https://openrouter.ai/api/v1",
        status="connected",
        config={"models": ["vendor/custom-model"]},
    )
    routing_session.add(provider)
    await routing_session.flush()
    routing_session.add(ModelDefinition(
        provider_id=provider.id,
        model_key="vendor/catalog-model",
        display_name="Catalog model",
    ))
    await routing_session.flush()

    entries = await ModelRegistryService(routing_session).list()

    assert [(item.model_id, item.display_name, item.enabled) for item in entries] == [
        ("vendor/custom-model", "vendor/custom-model", True)
    ]


@pytest.mark.asyncio
async def test_registry_sync_repairs_stale_auto_discovered_capabilities(routing_session):
    provider = ModelProvider(
        provider_type="openrouter",
        name="Primary OpenRouter",
        slug="repair-openrouter-capabilities",
        base_url="https://openrouter.ai/api/v1",
        status="connected",
        config={"models": ["qwen/qwen3-32b"]},
    )
    routing_session.add(provider)
    await routing_session.flush()
    definition = ModelDefinition(
        provider_id=provider.id,
        model_key="qwen/qwen3-32b",
        display_name="Qwen 3 32B",
        supports_tools=False,
        supports_json_mode=False,
    )
    stale = ModelRegistryEntry(
        model_id="qwen/qwen3-32b",
        display_name="Old Qwen",
        provider_id=provider.id,
        provider="openrouter",
        connection_type="api",
        enabled=False,
        capabilities={},
        quality_tier=3,
        cost_tier=3,
        latency_tier=3,
        context_window=8192,
        local=False,
        role_tags=[],
        config_json={"auto_discovered": True},
    )
    routing_session.add_all([definition, stale])
    await routing_session.flush()

    entries = await ModelRegistryService(routing_session).list()

    assert entries[0].display_name == "Qwen 3 32B"
    assert entries[0].enabled is True
    assert entries[0].capabilities["chat"] is True
    assert entries[0].capabilities["tool_use"] is True
    assert entries[0].capabilities["json_mode"] is True


@pytest.mark.asyncio
async def test_registry_sync_repairs_legacy_manual_row_missing_chat(routing_session):
    provider = ModelProvider(
        provider_type="ollama",
        name="gemma4:12b",
        slug="legacy-manual-gemma4-12b",
        base_url="http://127.0.0.1:11434",
        is_local=True,
        status="connected",
        config={"models": ["gemma4:12b"]},
    )
    routing_session.add(provider)
    await routing_session.flush()
    stale = ModelRegistryEntry(
        model_id="gemma4:12b",
        display_name="Gemma 4 12B",
        provider_id=provider.id,
        provider="ollama",
        connection_type="local",
        enabled=True,
        capabilities={},
        quality_tier=3,
        cost_tier=1,
        latency_tier=3,
        context_window=8192,
        local=True,
        role_tags=[],
        config_json={},
    )
    routing_session.add(stale)
    await routing_session.flush()

    result = await ModelRoutingService(routing_session).route(ModelRouteRequest(
        prompt="Extract and map data",
        task_type="stack_step_execution",
        required_capabilities=["chat"],
        profile_override="balanced",
    ))

    assert stale.capabilities["chat"] is True
    assert result.selected.id == stale.id
    assert result.selected.model_id == "gemma4:12b"


@pytest.mark.asyncio
async def test_custom_profile_survives_replaced_registry_uuid(routing_session):
    provider = ModelProvider(
        provider_type="ollama",
        name="gemma4:12b",
        slug="gemma4-12b-current",
        base_url="http://127.0.0.1:11434",
        is_local=True,
        status="connected",
        config={"models": ["gemma4:12b"]},
    )
    routing_session.add(provider)
    await routing_session.flush()
    old_provider_id = uuid.uuid4()
    old_entry = ModelRegistryEntry(
        model_id="gemma4:12b",
        display_name="Gemma 4 12B (old)",
        provider_id=old_provider_id,
        provider="ollama",
        connection_type="local",
        enabled=False,
        capabilities={"chat": True},
        quality_tier=3,
        cost_tier=1,
        latency_tier=3,
        context_window=8192,
        local=True,
        role_tags=[],
        config_json={"auto_discovered": True, "provider_available": False},
    )
    routing_session.add(old_entry)
    await routing_session.flush()
    custom = ModelRoutingProfile(
        name="Data Mapping",
        rules=[{
            "task_type": "*",
            "primary_model_id": str(old_entry.id),
            "fallback_model_ids": [],
        }],
        is_default=True,
    )
    routing_session.add(custom)
    await routing_session.flush()

    result = await ModelRoutingService(routing_session).route(
        ModelRouteRequest(
            prompt="Extract and map the supplied data",
            task_type="stack_step_execution",
            required_capabilities=["chat"],
            profile_override=str(custom.id),
        )
    )

    assert result.selected.model_id == "gemma4:12b"
    assert result.selected.provider_id == provider.id


@pytest.mark.asyncio
async def test_registry_sync_recovers_legacy_ollama_provider_model_name(routing_session):
    provider = ModelProvider(
        provider_type="ollama",
        name="qwen3:8b",
        slug="legacy-qwen3-8b",
        base_url="http://127.0.0.1:11434",
        is_local=True,
        status="connected",
        config={},
    )
    routing_session.add(provider)
    await routing_session.flush()

    entries = await ModelRegistryService(routing_session).list()

    assert len(entries) == 1
    assert entries[0].model_id == "qwen3:8b"
    assert entries[0].enabled is True
    assert entries[0].capabilities["chat"] is True


@pytest.mark.asyncio
async def test_registry_sync_recovers_legacy_cloud_provider_model_name(routing_session):
    providers = [
        ("openrouter", "z-ai/glm-5.2"),
        ("google", "gemini-3.5-flash"),
        ("openai", "gpt-5-mini"),
        ("anthropic", "claude-sonnet-4-5"),
    ]
    for provider_type, model_id in providers:
        routing_session.add(ModelProvider(
            provider_type=provider_type,
            name=model_id,
            slug=f"legacy-{provider_type}",
            base_url="https://example.test/v1",
            status="connected",
            config={},
        ))
    await routing_session.flush()

    entries = await ModelRegistryService(routing_session).list()

    assert {(item.provider, item.model_id, item.enabled) for item in entries} == {
        (provider_type, model_id, True) for provider_type, model_id in providers
    }
    assert legacy_provider_name_model_id("Primary OpenAI", "openai") is None


@pytest.mark.asyncio
async def test_registry_sync_treats_an_empty_model_list_as_explicit(routing_session):
    entry = await _model(routing_session, "vendor/old-model", quality=3, cost=2)
    provider = await routing_session.get(ModelProvider, entry.provider_id)
    provider.config = {"models": []}

    entries = await ModelRegistryService(routing_session).list()

    assert len(entries) == 1
    assert entries[0].enabled is False


@pytest.mark.asyncio
async def test_registry_sync_preserves_manual_toggle_across_provider_availability(routing_session):
    entry = await _model(routing_session, "vendor/selected-model", quality=3, cost=2)
    provider = await routing_session.get(ModelProvider, entry.provider_id)
    provider.config = {"models": [entry.model_id]}
    entry.enabled = False

    service = ModelRegistryService(routing_session)
    await service.sync_connected()
    assert entry.enabled is False

    provider.status = "disabled"
    await service.sync_connected()
    assert entry.enabled is False

    provider.status = "connected"
    await service.sync_connected()
    assert entry.enabled is False


@pytest.mark.asyncio
async def test_routing_excludes_disabled_models_and_disconnected_providers(routing_session):
    disconnected = await _model(routing_session, "vendor/disconnected", quality=5, cost=1)
    disconnected_provider = await routing_session.get(ModelProvider, disconnected.provider_id)
    disconnected_provider.status = "disabled"
    disabled = await _model(routing_session, "vendor/manually-disabled", quality=5, cost=1)
    disabled.enabled = False
    eligible = await _model(routing_session, "vendor/eligible", quality=3, cost=3)

    result = await ModelRoutingService(routing_session).route(ModelRouteRequest(prompt="Hello"))

    assert result.selected.id == eligible.id
    assert disconnected.enabled is False


@pytest.mark.asyncio
async def test_routing_honors_context_and_output_limits(routing_session):
    small = await _model(
        routing_session,
        "small-context",
        quality=5,
        cost=1,
        capabilities={"chat": True, "long_context": True},
    )
    small.context_window = 8_192
    small.max_output_tokens = 4_096
    large = await _model(
        routing_session,
        "large-context",
        quality=3,
        cost=2,
        capabilities={"chat": True, "long_context": True},
    )
    large.context_window = 65_536
    large.max_output_tokens = 8_192

    result = await ModelRoutingService(routing_session).route(
        ModelRouteRequest(prompt="Analyze this", context_size_estimate=12_000)
    )

    assert result.selected.id == large.id
    assert result.payload["selected_context_window"] == 65_536
    assert result.payload["selected_max_output_tokens"] == 8_192


@pytest.mark.asyncio
async def test_default_profiles_include_custom_with_balanced_active(routing_session):
    service = ModelRoutingService(routing_session)
    profiles = await service.ensure_defaults()
    assert {item.name for item in profiles} >= {
        "Ultra Economy", "Economy", "Balanced", "High Capability", "Premium", "Custom"
    }
    assert (await service.active_profile()).name == "Balanced"


@pytest.mark.asyncio
async def test_automatic_profiles_are_read_only_but_multiple_custom_profiles_are_allowed(routing_session):
    profiles = await ModelRoutingService(routing_session).ensure_defaults()
    balanced = next(item for item in profiles if item.name == "Balanced")
    service = ModelRoutingProfileService(routing_session)

    with pytest.raises(ValueError, match="read-only"):
        await service.update(balanced.id, rules=[])
    with pytest.raises(ValueError, match="cannot be deleted"):
        await service.delete(balanced.id)
    with pytest.raises(ValueError, match="reserved"):
        await service.create(name="Premium", rules=[])

    finance = await service.create(name="Finance", rules=[])
    engineering = await service.create(name="Engineering", rules=[])
    assert finance.id != engineering.id


@pytest.mark.asyncio
async def test_custom_profile_routes_only_across_operator_selected_models(routing_session):
    excluded = await _model(
        routing_session, "excluded-premium", quality=5, cost=1,
        capabilities={"chat": True, "coding": True},
    )
    primary = await _model(
        routing_session, "chosen-primary", quality=3, cost=3,
        capabilities={"chat": True, "coding": True},
    )
    fallback = await _model(
        routing_session, "chosen-fallback", quality=4, cost=2,
        capabilities={"chat": True, "coding": True},
    )
    service = ModelRoutingService(routing_session)
    profiles = await service.ensure_defaults()
    custom = next(item for item in profiles if item.name == "Custom")
    custom.rules = [{
        "task_type": "*",
        "primary_model_id": str(primary.id),
        "fallback_model_ids": [str(fallback.id)],
    }]

    result = await service.route(ModelRouteRequest(
        prompt="Implement the requested change", task_type="coding_edit", profile_override=str(custom.id)
    ))

    assert result.selected.id == primary.id
    assert excluded.id not in {result.selected.id, *(item.id for item in result.fallbacks)}
    assert {item.id for item in result.fallbacks} == {fallback.id}


@pytest.mark.asyncio
async def test_named_custom_profiles_keep_independent_strict_model_orders(routing_session):
    finance_primary = await _model(
        routing_session, "finance-primary", quality=3, cost=3,
        capabilities={"chat": True, "reasoning": True},
    )
    finance_fallback = await _model(
        routing_session, "finance-fallback", quality=4, cost=2,
        capabilities={"chat": True, "reasoning": True},
    )
    engineering = await _model(
        routing_session, "engineering-only", quality=5, cost=1,
        capabilities={"chat": True, "reasoning": True},
    )
    finance = ModelRoutingProfile(
        name="Finance",
        description="Finance-specialized route",
        rules=[{
            "task_type": "*",
            "primary_model_id": str(finance_primary.id),
            "fallback_model_ids": [str(finance_fallback.id)],
        }],
    )
    routing_session.add(finance)
    await routing_session.flush()

    result = await ModelRoutingService(routing_session).route(ModelRouteRequest(
        prompt="Review this financial model",
        required_capabilities=["chat", "reasoning"],
        profile_override=str(finance.id),
    ))

    assert result.selected.id == finance_primary.id
    assert [item.id for item in result.fallbacks] == [finance_fallback.id]
    assert engineering.id not in {result.selected.id, *(item.id for item in result.fallbacks)}


@pytest.mark.asyncio
async def test_empty_named_custom_profile_does_not_fall_back_to_all_models(routing_session):
    await _model(routing_session, "unscoped-model", quality=5, cost=1)
    finance = ModelRoutingProfile(name="Finance", rules=[])
    routing_session.add(finance)
    await routing_session.flush()

    with pytest.raises(NoEligibleModelError, match="Finance routing has no models configured"):
        await ModelRoutingService(routing_session).route(ModelRouteRequest(
            prompt="Review this financial model",
            profile_override=str(finance.id),
        ))


@pytest.mark.asyncio
async def test_automatic_profile_chat_exhaustion_allows_connected_provider_compatibility(routing_session):
    with pytest.raises(NoEligibleModelError) as captured:
        await ModelRoutingService(routing_session).route(ModelRouteRequest(
            prompt="Extract and map data",
            required_capabilities=["chat"],
            profile_override="balanced",
        ))

    assert captured.value.allow_connected_fallback is True


@pytest.mark.asyncio
async def test_registry_routing_target_uses_exact_provider_and_credential(routing_session):
    entry = await _model(
        routing_session, "vendor/secured-model", quality=4, cost=2,
        capabilities={"chat": True},
    )
    provider = await routing_session.get(ModelProvider, entry.provider_id)
    provider.config = {"models": [entry.model_id], "api_key": "provider-secret"}

    target = await _resolve_model_target(routing_session, entry.id)

    assert target is not None
    assert target[0].id == provider.id
    assert target[1] == entry.model_id
    assert target[3]["Authorization"] == "Bearer provider-secret"


@pytest.mark.asyncio
async def test_activating_profile_keeps_primary_shogun_assignment_in_sync(routing_session):
    agent = Agent(
        agent_type="shogun", name="Primary", slug="primary", status="active", is_primary=True
    )
    routing_session.add(agent)
    await routing_session.flush()

    await set_active_profile(ActiveProfileRequest(profile="custom"), routing_session)
    await routing_session.refresh(agent)
    custom = next(
        item for item in await ModelRoutingService(routing_session).ensure_defaults()
        if item.name == "Custom"
    )

    assert agent.model_routing_profile_id == custom.id
    assert custom.is_default is True


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
async def test_provider_label_is_never_routed_as_a_model_id(routing_session):
    provider = ModelProvider(
        id=uuid.uuid4(),
        provider_type="openrouter",
        name="OpenRouter",
        slug=f"provider-{uuid.uuid4().hex}",
        base_url="https://openrouter.ai/api/v1",
        is_local=False,
        status="connected",
        config={"models": ["google/gemini-3.5-flash"]},
    )
    stale = ModelRegistryEntry(
        model_id="OpenRouter",
        display_name="OpenRouter",
        provider_id=provider.id,
        provider="openrouter",
        connection_type="api",
        enabled=True,
        capabilities={"chat": True, "tool_use": True},
        quality_tier=5,
        cost_tier=1,
        latency_tier=1,
        context_window=128000,
        max_output_tokens=4096,
        local=False,
        role_tags=[],
        config_json={"auto_discovered": True},
    )
    routing_session.add_all([provider, stale])
    await routing_session.flush()

    result = await ModelRoutingService(routing_session).route(
        ModelRouteRequest(prompt="Hello", required_capabilities=["chat", "tool_use"])
    )

    assert is_concrete_model_id("OpenRouter", "openrouter") is False
    assert result.selected.model_id == "google/gemini-3.5-flash"


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
    model_summary = summary["by_model"][f"{strong.provider}:{strong.model_id}"]
    assert model_summary["peak_input_tokens"] == 100
    assert model_summary["average_context_percent"] == 0.1


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
