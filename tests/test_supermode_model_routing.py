"""Task-description routing-profile selection for Supermode."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import shogun.db.models  # noqa: F401 - register every FK target in metadata
from shogun.db.base import Base
from shogun.db.models.model_provider import ModelProvider
from shogun.db.models.model_router import ModelRegistryEntry
from shogun.db.models.model_routing import ModelRoutingProfile
from shogun.services.model_router import NoEligibleModelError
from shogun.supermode import worker as mission_worker
from shogun.supermode.model_routing import (
    SupermodeRoutingChoice,
    rank_supermode_routing_profiles,
)


@pytest.fixture
async def routing_session_factory(monkeypatch):
    config = {
        "active_profile": "balanced",
        "require_user_approval_for_premium": False,
    }
    monkeypatch.setattr("shogun.services.model_router.read_routing_config", lambda: config)
    monkeypatch.setattr("shogun.supermode.model_routing.read_routing_config", lambda: config)
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _task(title: str, objective: str, task_type: str, instructions: str = ""):
    return SimpleNamespace(
        title=title,
        objective=objective,
        instructions=instructions,
        task_type=task_type,
        required_capabilities=["chat"],
        required_tools=[],
    )


def _agent(*, profile_id: str | None = None, role: str = "Mission Specialist"):
    return SimpleNamespace(
        role_name=role,
        role_description="",
        objective="",
        routing_preferences={"model_routing_profile_id": profile_id} if profile_id else {},
    )


@pytest.mark.asyncio
async def test_supermode_chooses_different_custom_profiles_from_task_descriptions(
    routing_session_factory,
):
    async with routing_session_factory() as session:
        session.add_all(
            [
                ModelRoutingProfile(
                    name="Local Boys",
                    description="Use local low-cost models for economic inference.",
                    rules=[{"task_type": "*", "primary_model_id": "local-economic-model"}],
                ),
                ModelRoutingProfile(
                    name="Review Guard",
                    description="Rigorous critical review and adversarial verification.",
                    rules=[{"task_type": "*", "primary_model_id": "review-model"}],
                ),
            ]
        )
        await session.flush()
        mission = SimpleNamespace(objective="Prepare a complete investment recommendation")

        economic = await rank_supermode_routing_profiles(
            session,
            mission=mission,
            task=_task(
                "Run economic forecast",
                "Analyze economic viability and financial assumptions.",
                "mission_research",
            ),
            agent=_agent(role="Financial Analyst"),
        )
        review = await rank_supermode_routing_profiles(
            session,
            mission=mission,
            task=_task(
                "Critically review findings",
                "Perform an independent critical review.",
                "mission_critique",
                "Use rigorous adversarial verification.",
            ),
            agent=_agent(role="Skeptical Reviewer"),
        )

        assert economic[0].profile_name == "Local Boys"
        assert economic[0].source == "description_match"
        assert "economic" in economic[0].matched_terms
        assert review[0].profile_name == "Review Guard"
        assert review[0].source == "description_match"
        assert review[0].profile_id != economic[0].profile_id


@pytest.mark.asyncio
async def test_samurai_profile_is_preserved_until_a_stronger_description_match(
    routing_session_factory,
):
    async with routing_session_factory() as session:
        assigned = ModelRoutingProfile(
            name="Fleet Default",
            description="General fleet work.",
            rules=[{"task_type": "*", "primary_model_id": "fleet-model"}],
        )
        specialist = ModelRoutingProfile(
            name="Code Forge",
            description="Software implementation, coding, patches, and test repair.",
            rules=[{"task_type": "*", "primary_model_id": "coding-model"}],
        )
        session.add_all([assigned, specialist])
        await session.flush()
        mission = SimpleNamespace(objective="Maintain the product")
        agent = _agent(profile_id=str(assigned.id), role="Fleet Operator")

        general = await rank_supermode_routing_profiles(
            session,
            mission=mission,
            task=_task("Collect inputs", "Gather ordinary source material.", "mission_research"),
            agent=agent,
        )
        coding = await rank_supermode_routing_profiles(
            session,
            mission=mission,
            task=_task(
                "Implement software patch",
                "Write code and repair the failing tests.",
                "coding_edit",
            ),
            agent=agent,
        )

        assert general[0].profile_name == "Fleet Default"
        assert general[0].source == "samurai_preference"
        assert coding[0].profile_name == "Code Forge"
        assert coding[0].score > general[0].score


@pytest.mark.asyncio
async def test_supermode_tries_operator_fallback_when_preferred_profile_is_ineligible(
    routing_session_factory,
    monkeypatch,
):
    preferred = SupermodeRoutingChoice(
        profile_id="preferred-id",
        profile_name="Economic Local",
        profile_description="Local models for economic work",
        source="description_match",
        reason="Matched economic",
        score=0.9,
    )
    fallback = SupermodeRoutingChoice(
        profile_id="fallback-id",
        profile_name="Fleet Default",
        profile_description="Fleet fallback",
        source="samurai_preference",
        reason="Assigned to Samurai",
        score=0.64,
    )
    calls: list[str] = []

    async def resolve(_session, **kwargs):
        calls.append(kwargs["routing_profile_id"])
        if kwargs["routing_profile_id"] == preferred.profile_id:
            raise NoEligibleModelError("Preferred profile lacks tool use")
        return [(SimpleNamespace(provider_type="openai"), "fallback-model", "", {})], {
            "reason": "Fallback model is eligible"
        }

    monkeypatch.setattr("shogun.engine.flow_engine._resolve_task_llm_chain", resolve)
    async with routing_session_factory() as session:
        chain, routing, selected, failures = await mission_worker._resolve_profile_routed_chain(
            session,
            choices=[preferred, fallback],
            prompt="Analyze the task",
            task=SimpleNamespace(id="task-id", task_type="mission_research", retry_count=0),
            mission=SimpleNamespace(id="mission-id"),
            required_capabilities=["chat", "tool_use"],
            context_size_estimate=2000,
        )

    assert calls == [preferred.profile_id, fallback.profile_id]
    assert selected == fallback
    assert chain[0][1] == "fallback-model"
    assert routing["reason"] == "Fallback model is eligible"
    assert failures == [{
        "profile_name": "Economic Local",
        "reason": "Preferred profile lacks tool use",
    }]


@pytest.mark.asyncio
async def test_supermode_falls_back_from_small_context_custom_profile_to_balanced(
    routing_session_factory,
):
    async with routing_session_factory() as session:
        small_provider = ModelProvider(
            provider_type="openrouter",
            name="Small Context Provider",
            slug="small-context-provider",
            base_url="https://example.test/v1",
            status="connected",
            config={"models": ["small-context-model"]},
        )
        large_provider = ModelProvider(
            provider_type="openrouter",
            name="Large Context Provider",
            slug="large-context-provider",
            base_url="https://example.test/v1",
            status="connected",
            config={"models": ["large-context-model"]},
        )
        session.add_all([small_provider, large_provider])
        await session.flush()
        small_model = ModelRegistryEntry(
            model_id="small-context-model",
            display_name="Small Context Model",
            provider_id=small_provider.id,
            provider="openrouter",
            connection_type="api",
            enabled=True,
            capabilities={"chat": True},
            quality_tier=3,
            cost_tier=2,
            latency_tier=2,
            context_window=8192,
            max_output_tokens=4096,
            local=False,
            role_tags=[],
            config_json={"provider_available": True},
        )
        large_model = ModelRegistryEntry(
            model_id="large-context-model",
            display_name="Large Context Model",
            provider_id=large_provider.id,
            provider="openrouter",
            connection_type="api",
            enabled=True,
            capabilities={"chat": True},
            quality_tier=4,
            cost_tier=2,
            latency_tier=2,
            context_window=128000,
            max_output_tokens=4096,
            local=False,
            role_tags=[],
            config_json={"provider_available": True},
        )
        session.add_all([small_model, large_model])
        await session.flush()
        compact = ModelRoutingProfile(
            name="Compact Fleet Route",
            description="General fleet work.",
            rules=[{
                "task_type": "*",
                "primary_model_id": str(small_model.id),
                "fallback_model_ids": [],
            }],
        )
        session.add(compact)
        await session.flush()
        task = _task("Collect market evidence", "Research the market.", "mission_research")
        task.id = uuid.uuid4()
        task.retry_count = 0
        mission = SimpleNamespace(id=uuid.uuid4(), objective="Prepare a market plan")
        agent = _agent(profile_id=str(compact.id), role="Lead Researcher")
        choices = await rank_supermode_routing_profiles(
            session,
            mission=mission,
            task=task,
            agent=agent,
        )

        chain, _routing, selected, failures = await mission_worker._resolve_profile_routed_chain(
            session,
            choices=choices,
            prompt="Analyze the market evidence",
            task=task,
            mission=mission,
            required_capabilities=["chat"],
            context_size_estimate=6000,
        )

    assert choices[0].profile_name == "Compact Fleet Route"
    assert selected.profile_name == "Balanced"
    assert chain[0][1] == large_model.model_id
    assert failures[0]["profile_name"] == "Compact Fleet Route"
    assert "enough context capacity" in failures[0]["reason"]


@pytest.mark.asyncio
async def test_supermode_uses_premium_only_when_explicit_and_policy_allows_it(
    routing_session_factory,
    monkeypatch,
):
    task = _task(
        "Maximum-quality final review",
        "Use the premium strategy and strongest quality for this critical decision.",
        "mission_critique",
    )
    mission = SimpleNamespace(objective="Validate the final decision")
    async with routing_session_factory() as session:
        allowed = await rank_supermode_routing_profiles(
            session,
            mission=mission,
            task=task,
            agent=_agent(role="Skeptical Reviewer"),
        )
        monkeypatch.setattr(
            "shogun.supermode.model_routing.read_routing_config",
            lambda: {
                "active_profile": "balanced",
                "require_user_approval_for_premium": True,
            },
        )
        approval_required = await rank_supermode_routing_profiles(
            session,
            mission=mission,
            task=task,
            agent=_agent(role="Skeptical Reviewer"),
        )

    assert allowed[0].profile_name == "Premium"
    assert approval_required[0].profile_name != "Premium"
