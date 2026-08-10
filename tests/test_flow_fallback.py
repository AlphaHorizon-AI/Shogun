from __future__ import annotations

import re
import uuid
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.db.models.model_routing import ModelRoutingProfile
from shogun.engine import flow_engine
from shogun.services import notification_service, posture_guard
from shogun.services.model_router import NoEligibleModelError
from shogun.services.model_service import ModelRoutingProfileService


class _SessionContext:
    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_provider_connection_resolves_protected_api_key(monkeypatch):
    provider = SimpleNamespace(
        config={"api_key": "enc:protected-value", "model": "test-model"},
        base_url="https://openrouter.ai/api/v1",
        provider_type="openrouter",
        name="OpenRouter",
    )
    seen_configs: list[dict] = []

    def resolve_api_key(config):
        seen_configs.append(config)
        return "decrypted-api-key"

    monkeypatch.setattr(flow_engine, "provider_api_key", resolve_api_key)

    _, model, _, headers = flow_engine._provider_connection(provider)

    assert seen_configs == [provider.config]
    assert model == "test-model"
    assert headers["Authorization"] == "Bearer decrypted-api-key"


def test_provider_connection_accepts_bearer_token_credentials():
    provider = SimpleNamespace(
        config={"access_token": "provider-access-token", "model": "test-model"},
        base_url="https://provider.invalid/v1",
        provider_type="custom",
        name="Token Provider",
    )

    _, _, _, headers = flow_engine._provider_connection(provider)

    assert headers["Authorization"] == "Bearer provider-access-token"


@pytest.mark.asyncio
async def test_task_router_chat_exhaustion_uses_connected_provider_chain(monkeypatch):
    provider = SimpleNamespace(name="Gemma 4", provider_type="ollama")
    expected_chain = [(provider, "gemma4:12b", "http://127.0.0.1:11434/v1", {})]

    class EmptyRegistryRouter:
        def __init__(self, _session):
            pass

        async def route(self, _request):
            raise NoEligibleModelError(
                "No eligible model found for this task. Required capabilities: chat.",
                allow_connected_fallback=True,
            )

    async def legacy_chain(_session, _profile_id=None):
        return expected_chain

    from shogun.services import model_router

    monkeypatch.setattr(model_router, "ModelRoutingService", EmptyRegistryRouter)
    monkeypatch.setattr(flow_engine, "_resolve_llm_chain", legacy_chain)

    chain, routing = await flow_engine._resolve_task_llm_chain(
        object(),
        prompt="Extract and map data",
        task_type="stack_step_execution",
        required_capabilities=["chat"],
    )

    assert chain == expected_chain
    assert routing["selected_model"] == "gemma4:12b"
    assert routing["active_profile"] == "connected_provider_compatibility"


@pytest.mark.asyncio
async def test_task_router_policy_failure_does_not_use_compatibility_chain(monkeypatch):
    class BlockedRouter:
        def __init__(self, _session):
            pass

        async def route(self, _request):
            raise NoEligibleModelError("Daily model budget reached.")

    async def forbidden_legacy_chain(*_args, **_kwargs):
        raise AssertionError("Policy failures must not reach the legacy chain")

    from shogun.services import model_router

    monkeypatch.setattr(model_router, "ModelRoutingService", BlockedRouter)
    monkeypatch.setattr(flow_engine, "_resolve_llm_chain", forbidden_legacy_chain)

    with pytest.raises(NoEligibleModelError, match="Daily model budget"):
        await flow_engine._resolve_task_llm_chain(
            object(),
            prompt="Extract and map data",
            required_capabilities=["chat"],
        )


def test_exhausted_retry_policy_is_terminal():
    actions = {
        name: flow_engine._node_failure_action(config)
        for name, config in {
            "retry": {"failure_action": "retry"},
            "stop": {"failure_action": "stop"},
            "legacy_stop": {"on_failure": "fail_parent"},
            "continue": {"failure_action": "continue"},
            "skip": {"failure_action": "skip"},
        }.items()
    }

    assert flow_engine._failure_action_is_terminal(actions["retry"]) is True
    assert flow_engine._failure_action_is_terminal(actions["stop"]) is True
    assert flow_engine._failure_action_is_terminal(actions["legacy_stop"]) is True
    assert flow_engine._failure_action_is_terminal(actions["continue"]) is False
    assert flow_engine._failure_action_is_terminal(actions["skip"]) is False


def test_flow_generation_settings_replace_inherited_seed():
    context = {"flow_seed": 1, "flow_seed_model_id": "old-model"}
    flow_engine._apply_flow_generation_settings(
        context,
        SimpleNamespace(seed=42, seed_model_id="provider-id:gemma4:12b"),
    )
    assert context["flow_seed"] == 42
    assert context["flow_seed_model_id"] == "provider-id:gemma4:12b"


@pytest.mark.asyncio
async def test_model_call_applies_profile_temperature_and_matching_flow_seed(monkeypatch):
    provider_id = uuid.uuid4()
    provider = SimpleNamespace(id=provider_id, name="Local Ollama", provider_type="ollama")
    calls: list[dict] = []

    async def call_llm(*_args, **kwargs):
        calls.append(kwargs)
        return "stable response"

    async def record_usage(*_args, **_kwargs):
        return None

    monkeypatch.setattr(flow_engine, "_call_llm", call_llm)
    monkeypatch.setattr(flow_engine, "_record_model_usage", record_usage)
    route_key = f"{provider_id}:gemma4:12b"
    result = await flow_engine._call_llm_chain(
        [{"role": "user", "content": "Repeatable work"}],
        [(provider, "gemma4:12b", "http://localhost:11434/v1", {})],
        timeout=30,
        retry_count=0,
        context="Seeded AgentFlow",
        routing_context={
            "request_parameters": {route_key: {"temperature": 0.1}},
            "flow_seed": 12345,
            "flow_seed_model_id": route_key,
        },
    )
    assert result == "stable response"
    assert calls[0]["temperature"] == 0.1
    assert calls[0]["seed"] == 12345


@pytest.mark.asyncio
async def test_model_call_omits_flow_seed_when_physical_model_does_not_match(monkeypatch):
    provider_id = uuid.uuid4()
    provider = SimpleNamespace(id=provider_id, name="Fallback API", provider_type="openrouter")
    calls: list[dict] = []

    async def call_llm(*_args, **kwargs):
        calls.append(kwargs)
        return "fallback response"

    async def record_usage(*_args, **_kwargs):
        return None

    monkeypatch.setattr(flow_engine, "_call_llm", call_llm)
    monkeypatch.setattr(flow_engine, "_record_model_usage", record_usage)
    route_key = f"{provider_id}:fallback-model"
    await flow_engine._call_llm_chain(
        [{"role": "user", "content": "Repeatable work"}],
        [(provider, "fallback-model", "https://example.test/v1", {})],
        timeout=30,
        retry_count=0,
        context="Seeded AgentFlow fallback",
        routing_context={
            "request_parameters": {route_key: {"temperature": 0.2}},
            "flow_seed": 12345,
            "flow_seed_model_id": "different-provider:different-model",
        },
    )
    assert calls[0]["temperature"] == 0.2
    assert calls[0]["seed"] is None


@pytest.mark.asyncio
async def test_samurai_falls_back_after_timeout(monkeypatch):
    calls: list[tuple[str, int]] = []
    fallback_events: list[dict] = []

    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())

    async def resolve_chain(_session, _profile_id=None):
        return [
            (object(), "primary-model", "https://primary.invalid/v1", {}),
            (object(), "fallback-model", "https://fallback.invalid/v1", {}),
        ]

    async def call_llm(_messages, model_name, _base_url, _headers, timeout):
        calls.append((model_name, timeout))
        if model_name == "primary-model":
            raise httpx.ReadTimeout("primary timed out")
        return "fallback response"

    async def notify(**kwargs):
        fallback_events.append(kwargs)

    monkeypatch.setattr(flow_engine, "_resolve_llm_chain", resolve_chain)
    monkeypatch.setattr(flow_engine, "_call_llm", call_llm)
    monkeypatch.setattr(notification_service, "notify_model_fallback", notify)

    result = await flow_engine._exec_samurai(
        {"task_description": "Do the work", "timeout": 7, "retry_count": 0},
        "",
    )

    assert result == "fallback response"
    assert calls == [("primary-model", 7), ("fallback-model", 7)]
    assert fallback_events[0]["from_model"] == "primary-model"
    assert fallback_events[0]["to_model"] == "fallback-model"
    assert fallback_events[0]["reason"] == "timeout after 7s"


@pytest.mark.asyncio
async def test_samurai_exhausts_retries_before_fallback(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())

    async def resolve_chain(_session, _profile_id=None):
        return [
            (object(), "primary", "https://primary.invalid/v1", {}),
            (object(), "fallback", "https://fallback.invalid/v1", {}),
        ]

    async def call_llm(_messages, model_name, _base_url, _headers, _timeout):
        calls.append(model_name)
        if model_name == "primary":
            raise ValueError("provider unavailable")
        return "ok"

    async def notify(**_kwargs):
        return None

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(flow_engine, "_resolve_llm_chain", resolve_chain)
    monkeypatch.setattr(flow_engine, "_call_llm", call_llm)
    monkeypatch.setattr(notification_service, "notify_model_fallback", notify)
    monkeypatch.setattr(flow_engine.asyncio, "sleep", no_sleep)

    assert await flow_engine._exec_samurai(
        {"task_description": "Do the work", "timeout": 12, "retry_count": 1},
        "",
    ) == "ok"
    assert calls == ["primary", "primary", "fallback"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "routing_error",
    [
        "No enabled model has enough context capacity for this input",
        "No eligible model found for this task. Required capabilities: chat, long_context.",
    ],
    ids=["capacity-exhausted", "long-context-capability"],
)
async def test_samurai_chunks_context_that_exceeds_every_single_request(monkeypatch, routing_error):
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    route_calls: list[int] = []
    model_chain = [(object(), "chunk-model", "https://model.invalid/v1", {})]

    async def resolve_route(*_args, **kwargs):
        route_calls.append(kwargs["context_size_estimate"])
        if len(route_calls) == 1:
            raise NoEligibleModelError(routing_error)
        return model_chain, {
            "selected_context_window": 2048,
            "selected_max_input_tokens": 1536,
            "selected_max_output_tokens": 512,
        }

    prompts: list[str] = []

    async def call_chain(messages, *_args, **_kwargs):
        prompts.append(messages[1]["content"])
        return f"row-{len(prompts)}"

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain", call_chain)

    source = "\n\n".join(f"record {index}: " + ("x" * 300) for index in range(30))
    progress: list[int] = []

    async def record_progress(completed: int, total: int):
        progress.append(round((completed / total) * 100))

    result = await flow_engine._exec_samurai(
        {"task_description": "Extract every record"},
        source,
        progress_callback=record_progress,
    )

    assert route_calls[0] > 0 and route_calls[1] == 0
    assert len(prompts) > 1
    assert all("do not summarize, sample, or omit" in prompt for prompt in prompts)
    assert result == "\n".join(f"row-{index}" for index in range(1, len(prompts) + 1))
    assert progress[0] == 1
    assert progress[-1] == 100
    assert progress == sorted(progress)


@pytest.mark.asyncio
async def test_samurai_chunking_survives_stale_registry_chat_gate(monkeypatch):
    session_context = _SessionContext()
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: session_context)
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Local Ollama",
        provider_type="ollama",
        config={"context_window": 8192},
    )
    route_calls = 0

    async def resolve_route(*_args, **_kwargs):
        nonlocal route_calls
        route_calls += 1
        if route_calls == 1:
            raise NoEligibleModelError("No enabled model has enough context capacity for this input")
        raise NoEligibleModelError("No eligible model found for this task. Required capabilities: chat.")

    async def resolve_connected(*_args, **_kwargs):
        return [(provider, "gemma-test", "http://localhost:11434/v1", {})]

    prompts: list[str] = []

    async def call_chain(messages, *_args, **_kwargs):
        prompts.append(messages[1]["content"])
        return "mapped-row"

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_resolve_llm_chain", resolve_connected)
    monkeypatch.setattr(flow_engine, "_call_llm_chain", call_chain)

    result = await flow_engine._exec_samurai(
        {"task_description": "Extract every record"},
        "\n\n".join("record " + ("x" * 1000) for _ in range(50)),
    )

    # The compatibility chain is established once, then eligibility is
    # refreshed for each actual chunk. A stale registry still falls back to
    # the established connected provider chain.
    assert route_calls == 2 + len(prompts)
    assert len(prompts) > 1
    assert result.startswith("mapped-row")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "recoverable_error",
    [
        httpx.ReadTimeout(""),
        ValueError("LLM API error 400: prompt exceeds maximum context length"),
    ],
    ids=["timeout", "provider-context-rejection"],
)
async def test_samurai_bisects_and_retries_a_recoverable_chunk(monkeypatch, recoverable_error):
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Local Ollama",
        provider_type="ollama",
        is_local=True,
        config={},
    )

    async def resolve_route(*_args, **_kwargs):
        return [(provider, "gemma-test", "http://localhost:11434/v1", {})], {
            "selected_context_window": 32_768,
            "selected_max_input_tokens": 24_576,
            "selected_max_output_tokens": 4_096,
        }

    calls: list[int] = []

    async def call_chain(messages, *_args, **_kwargs):
        content_length = len(messages[1]["content"])
        calls.append(content_length)
        if len(calls) == 1:
            raise flow_engine.ModelCallError(
                context="AgentFlow Samurai node chunk 1/1",
                provider="Local Ollama",
                model="gemma-test",
                timeout=300,
                cause=recoverable_error,
                input_characters=content_length,
            )
        return "recovered-row"

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain", call_chain)

    source = "\n\n".join("record " + ("x" * 1000) for _ in range(120))
    result = await flow_engine._exec_samurai({"task_description": "Extract every record"}, source)

    assert len(calls) >= 3
    assert calls[1] < calls[0] and calls[2] < calls[0]
    assert result.count("recovered-row") >= 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("node_timeout", "local_chunk_timeout", "expected_timeout"),
    [(300, 900, 900), (1200, 600, 1200)],
)
async def test_samurai_uses_configurable_local_document_chunk_timeout(
    monkeypatch,
    node_timeout,
    local_chunk_timeout,
    expected_timeout,
):
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Local Ollama",
        provider_type="ollama",
        is_local=True,
        config={},
    )

    async def resolve_route(*_args, **_kwargs):
        return [(provider, "gemma-test", "http://localhost:11434/v1", {})], {
            "selected_context_window": 16_384,
            "selected_max_input_tokens": 12_288,
            "selected_max_output_tokens": 2_048,
        }

    timeouts: list[int] = []

    async def call_chain(_messages, *_args, **kwargs):
        timeouts.append(kwargs["timeout"])
        return "mapped-row"

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain", call_chain)

    source = "\n\n".join("record " + ("x" * 1000) for _ in range(80))
    await flow_engine._exec_samurai(
        {
            "task_description": "Extract every record",
            "timeout": node_timeout,
            "local_chunk_timeout": local_chunk_timeout,
        },
        source,
    )

    assert timeouts and set(timeouts) == {expected_timeout}


@pytest.mark.asyncio
async def test_local_excel_matrix_uses_adaptive_batches_bounded_output_and_visible_progress(monkeypatch):
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Local Ollama",
        provider_type="ollama",
        is_local=True,
        config={},
    )

    async def resolve_route(*_args, **_kwargs):
        return [(provider, "gemma-test", "http://localhost:11434/v1", {})], {
            "selected_context_window": 262_144,
            "selected_max_input_tokens": 196_608,
            "selected_max_output_tokens": 65_536,
        }

    calls: list[dict] = []

    async def call_rows(messages, *_args, **kwargs):
        calls.append({"message": messages[-1]["content"], "max_tokens": kwargs["max_tokens"]})
        return [["A", 1]]

    progress: list[tuple[int, int]] = []

    async def record_progress(completed, total):
        progress.append((completed, total))

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain_rows", call_rows)

    source = "\n\n".join("record " + ("x" * 1000) for _ in range(24))
    fixed_context = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind": "excel", "logical_columns": 2}
"""

    result = await flow_engine._exec_samurai(
        {"task_description": "Extract every source record."},
        source,
        fixed_context_str=fixed_context,
        progress_callback=record_progress,
    )

    # The adaptive executor no longer forces tiny 2K-token batches. This
    # fixture fits into one safe local batch.
    assert len(calls) == 1
    assert {call["max_tokens"] for call in calls} == {8192}
    assert all(len(call["message"]) < 40_000 for call in calls)
    assert progress[0][0] > 0
    assert progress[-1][0] == progress[-1][1]
    assert __import__("json").loads(result) == [["A", 1]] * len(calls)


@pytest.mark.asyncio
async def test_one_shot_template_is_planned_once_and_example_is_not_repeated_per_chunk(monkeypatch):
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Local Ollama",
        provider_type="ollama",
        is_local=True,
        config={},
    )

    async def resolve_route(*_args, **_kwargs):
        return [
            (provider, "gemma-test", "http://localhost:11434/v1", {}),
            (
                SimpleNamespace(id=uuid.uuid4(), name="Cloud", provider_type="openrouter"),
                "cloud-test",
                "https://cloud.invalid/v1",
                {},
            ),
        ], {
            "selected_context_window": 32_768,
            "selected_max_input_tokens": 24_576,
            "selected_max_output_tokens": 4_096,
            "fallback_models": [{"model_id": "cloud-test", "max_input_tokens": 8_192}],
        }

    prompts: list[str] = []
    chain_sizes: list[int] = []

    async def call_rows(messages, chain, *_args, **_kwargs):
        prompt = messages[-1]["content"]
        prompts.append(prompt)
        chain_sizes.append(len(chain))
        if "Create a reusable mapping plan" in prompt:
            return [
                [0, "Item", "source item", "copy exactly"],
                [1, "Quantity", "source quantity", "parse as number"],
            ]
        return [["A", 1]]

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain_rows", call_rows)

    fixed_context = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind": "excel", "logical_columns": 2}
[POPULATED ONE-SHOT EXAMPLE]
REFERENCE-ONLY-VALUE | 99
"""
    source = "\n\n".join("record " + ("x" * 1000) for _ in range(30))

    result = await flow_engine._exec_samurai(
        {"task_description": "Extract every source record.", "local_matrix_chunk_tokens": 2048},
        source,
        fixed_context_str=fixed_context,
    )

    planning_prompts = [item for item in prompts if "Create a reusable mapping plan" in item]
    extraction_prompts = [item for item in prompts if "CONTEXT FROM PREVIOUS STEPS (chunk" in item]
    assert len(planning_prompts) == 1
    assert extraction_prompts
    assert all("REFERENCE-ONLY-VALUE" not in item for item in extraction_prompts)
    assert all("APPROVED TRANSFORMATION PLAN" in item for item in extraction_prompts)
    assert all(size == 2 for size in chain_sizes)
    assert __import__("json").loads(result) == [["A", 1]] * len(extraction_prompts)


@pytest.mark.asyncio
async def test_remote_exhaustive_matrix_is_bounded_parallel_and_complete(monkeypatch):
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Remote Matrix Model",
        provider_type="openai_compatible",
        is_local=False,
        config={},
    )

    async def resolve_route(*_args, **_kwargs):
        return [(provider, "matrix-model", "https://model.invalid/v1", {})], {
            "selected_context_window": 262_144,
            "selected_max_input_tokens": 196_608,
            "selected_max_output_tokens": 65_536,
        }

    active_calls = 0
    max_active_calls = 0
    chunk_unit_counts: list[int] = []

    async def call_rows(messages, *_args, **_kwargs):
        nonlocal active_calls, max_active_calls
        prompt = messages[-1]["content"]
        unit_count = len(re.findall(r"(?m)^--- Page \d+ ---$", prompt))
        chunk_unit_counts.append(unit_count)
        active_calls += 1
        max_active_calls = max(max_active_calls, active_calls)
        await flow_engine.asyncio.sleep(0.01)
        active_calls -= 1
        return [[f"material-{index}", index] for index in range(unit_count)]

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain_rows", call_rows)

    source = "\n".join(
        f"--- Page {index + 1} ---\nRecord: {140000 + index}\nLine: order-{index}"
        for index in range(12)
    )
    fixed_context = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind": "excel", "logical_columns": 2}
"""

    result = await flow_engine._exec_samurai(
        {
            "task_description": "Extract every record from the complete document.",
            "matrix_chunk_max_units": 3,
            "matrix_chunk_concurrency": 3,
        },
        source,
        fixed_context_str=fixed_context,
    )

    assert sorted(chunk_unit_counts) == [3, 3, 3, 3]
    assert max_active_calls > 1
    assert len(__import__("json").loads(result)) == 12


@pytest.mark.asyncio
async def test_exhaustive_matrix_rejects_shaped_but_incomplete_rows(monkeypatch):
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Remote Matrix Model",
        provider_type="openai_compatible",
        is_local=False,
        config={},
    )

    async def resolve_route(*_args, **_kwargs):
        return [(provider, "matrix-model", "https://model.invalid/v1", {})], {
            "selected_context_window": 262_144,
            "selected_max_input_tokens": 196_608,
            "selected_max_output_tokens": 65_536,
        }

    async def call_rows(*_args, **_kwargs):
        return []

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain_rows", call_rows)
    source = "\n".join(
        f"--- Page {index + 1} ---\nRecord: {140000 + index}\nLine: order-{index}"
        for index in range(10)
    )
    fixed_context = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind": "excel", "logical_columns": 2}
"""

    with pytest.raises(flow_engine.IncompleteMatrixOutputError, match="visibly incomplete|requires at least"):
        await flow_engine._exec_samurai(
            {
                "task_description": "Extract every record from the complete document.",
                "matrix_chunk_max_units": 10,
                "matrix_chunk_concurrency": 1,
            },
            source,
            fixed_context_str=fixed_context,
        )


def test_profile_coverage_counts_required_rows_not_source_sections():
    source = """Account: A1
D A1 order-1
Account: A2
D A2 order-2
"""
    task = "Extract every record from the complete document."
    profile = {
        "id": "account_demand_v1",
        "adapter": "sectioned_record_matrix_v1",
        "parameters": {
            "section_pattern": r"(?m)^Account: (?P<section_id>\S+)",
            "record_pattern": r"(?m)^(?P<kind>D) (?P<account>\S+) (?P<reference>\S+)$",
            "record_section_key_group": "account",
            "row_rules": [{"kind": "aggregate", "match": {"kind": "D"}}],
        },
    }
    config = {"_transformation_profiles": [profile]}

    minimum, evidence, label = flow_engine._minimum_matrix_rows_for_source(source, task, config)

    assert (minimum, evidence, label) == (2, 2, "profile-required row(s)")
    with pytest.raises(flow_engine.IncompleteMatrixOutputError, match="requires at least 2"):
        flow_engine._validate_matrix_coverage(
            [["only-one-row"]],
            source,
            task,
            config,
            label="test chunk",
        )


@pytest.mark.asyncio
async def test_incomplete_chunk_can_split_to_individual_source_pages(monkeypatch):
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Remote Matrix Model",
        provider_type="openai_compatible",
        is_local=False,
        config={},
    )

    async def resolve_route(*_args, **_kwargs):
        return [(provider, "matrix-model", "https://model.invalid/v1", {})], {
            "selected_context_window": 262_144,
            "selected_max_input_tokens": 196_608,
            "selected_max_output_tokens": 65_536,
        }

    attempted_unit_counts: list[int] = []
    corrective_prompts: list[str] = []

    async def call_rows(messages, *_args, **_kwargs):
        prompt = messages[-1]["content"]
        unit_count = len(re.findall(r"(?m)^--- Page \d+ ---$", prompt))
        attempted_unit_counts.append(unit_count)
        if "--- CORRECTIVE RETRY ---" in prompt:
            corrective_prompts.append(prompt)
        if unit_count == 1 and "Record: 140000" in prompt and not corrective_prompts:
            return []
        return [["one-row", 1]]

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain_rows", call_rows)
    source = "\n".join(
        f"--- Page {index + 1} ---\nRecord: {140000 + index}\nLine: order-{index}"
        for index in range(10)
    )
    task = "Extract every record from the complete document."
    fixed_context = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind": "excel", "logical_columns": 2}
"""

    result = await flow_engine._exec_samurai(
        {
            "task_description": task,
            "matrix_chunk_max_units": 10,
            "matrix_chunk_concurrency": 1,
            "minimum_source_coverage_ratio": 1.0,
        },
        source,
        fixed_context_str=fixed_context,
    )

    assert 10 in attempted_unit_counts
    assert 1 in attempted_unit_counts
    assert corrective_prompts
    assert "requires at least 1 output row" in corrective_prompts[0]
    assert len(__import__("json").loads(result)) == 10


@pytest.mark.asyncio
async def test_incomplete_leaf_retains_partial_rows_and_requests_only_missing_rows(monkeypatch):
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Remote Matrix Model",
        provider_type="openai_compatible",
        is_local=False,
        config={},
    )

    async def resolve_route(*_args, **_kwargs):
        return [(provider, "matrix-model", "https://model.invalid/v1", {})], {
            "selected_context_window": 262_144,
            "selected_max_input_tokens": 196_608,
            "selected_max_output_tokens": 65_536,
        }

    prompts: list[str] = []

    async def call_rows(messages, *_args, **_kwargs):
        prompt = messages[-1]["content"]
        prompts.append(prompt)
        if "Record: 140000" not in prompt:
            return [["other-planning", 3], ["other-detail", 4]]
        if "--- RETAINED VALID ROWS ---" in prompt:
            return [["missing-planning", 2]]
        return [["retained-stock", 1]]

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain_rows", call_rows)
    source = """--- Page 1 ---
Record: 140000
Line: order-1
--- Page 2 ---
Record: 140001
Line: order-2
"""
    task = "Extract every record and detail from the complete document."
    fixed_context = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind": "excel", "logical_columns": 2}
"""

    result = await flow_engine._exec_samurai(
        {
            "task_description": task,
            "matrix_chunk_max_units": 1,
            "matrix_chunk_concurrency": 1,
            "minimum_matrix_rows": 2,
        },
        source,
        fixed_context_str=fixed_context,
    )

    rows = __import__("json").loads(result)
    assert rows == [
        ["retained-stock", 1],
        ["missing-planning", 2],
        ["other-planning", 3],
        ["other-detail", 4],
    ]
    corrective_prompt = next(prompt for prompt in prompts if "--- RETAINED VALID ROWS ---" in prompt)
    assert "At least 1 additional row(s)" in corrective_prompt
    assert '["retained-stock", 1]' in corrective_prompt


@pytest.mark.asyncio
async def test_malformed_matrix_chunk_is_subdivided_instead_of_using_general_tools(monkeypatch):
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Remote Matrix Model",
        provider_type="openai_compatible",
        is_local=False,
        config={},
    )

    async def resolve_route(*_args, **_kwargs):
        return [(provider, "matrix-model", "https://model.invalid/v1", {})], {
            "selected_context_window": 262_144,
            "selected_max_input_tokens": 196_608,
            "selected_max_output_tokens": 65_536,
        }

    attempted_unit_counts: list[int] = []

    async def call_rows(messages, *_args, **_kwargs):
        prompt = messages[-1]["content"]
        unit_count = len(re.findall(r"(?m)^--- Page \d+ ---$", prompt))
        attempted_unit_counts.append(unit_count)
        if unit_count > 5:
            raise flow_engine.ModelCallError(
                context="AgentFlow Samurai node chunk 1/1",
                provider="Remote Matrix Model",
                model="matrix-model",
                timeout=300,
                cause=ValueError("The model did not submit rows or valid JSON rows"),
                input_characters=len(prompt),
            )
        return [[f"material-{index}", index] for index in range(unit_count)]

    async def forbidden_general_tool_repair(*_args, **_kwargs):
        raise AssertionError("Malformed row matrices must not be sent to general Samurai tools")

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain_rows", call_rows)
    monkeypatch.setattr(flow_engine, "_call_llm_chain_with_tools", forbidden_general_tool_repair)
    source = "\n".join(
        f"--- Page {index + 1} ---\nRecord: {140000 + index}\nLine: order-{index}"
        for index in range(10)
    )
    fixed_context = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind": "excel", "logical_columns": 2}
"""

    result = await flow_engine._exec_samurai(
        {
            "task_description": "Extract every record from the complete document.",
            "matrix_chunk_max_units": 10,
            "matrix_chunk_concurrency": 1,
        },
        source,
        fixed_context_str=fixed_context,
    )

    assert attempted_unit_counts == [10, 5, 5]
    assert len(__import__("json").loads(result)) == 10


def test_json_decode_failure_is_classified_as_malformed_matrix_output():
    decode_error = __import__("json").JSONDecodeError("Expecting value", "[]\nnot-json", 3)
    error = flow_engine.ModelCallError(
        context="AgentFlow Samurai node chunk 9/30",
        provider="Remote Matrix Model",
        model="matrix-model",
        timeout=600,
        cause=decode_error,
        input_characters=32_961,
    )

    assert flow_engine._is_structured_rows_failure(error) is True


@pytest.mark.asyncio
async def test_samurai_resumes_completed_matrix_chunks_from_checkpoint(monkeypatch, tmp_path):
    from shogun.config import settings

    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: _SessionContext())
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        name="Local Ollama",
        provider_type="ollama",
        is_local=True,
        config={},
    )

    async def resolve_route(*_args, **_kwargs):
        return [(provider, "gemma-test", "http://localhost:11434/v1", {})], {
            "selected_context_window": 32_768,
            "selected_max_input_tokens": 24_576,
            "selected_max_output_tokens": 4_096,
        }

    calls: list[str] = []
    fail_second_chunk = True

    async def call_rows(messages, *_args, **_kwargs):
        nonlocal fail_second_chunk
        prompt = messages[-1]["content"]
        label = next(
            (item for item in re.findall(r"chunk \d+/\d+", prompt) if item),
            "unknown",
        )
        calls.append(label)
        if label.startswith("chunk 2/") and fail_second_chunk:
            fail_second_chunk = False
            raise flow_engine.ModelCallError(
                context="AgentFlow Samurai node chunk 2",
                provider="Local Ollama",
                model="gemma-test",
                timeout=300,
                cause=ValueError("temporary invalid structured response"),
                input_characters=len(prompt),
            )
        return [[label, 1]]

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", resolve_route)
    monkeypatch.setattr(flow_engine, "_call_llm_chain_rows", call_rows)

    fixed_context = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind": "excel", "logical_columns": 2}
"""
    source = "\n\n".join(f"record {index} " + ("x" * 1000) for index in range(30))
    config = {
        "task_description": "Extract every source record.",
        "local_matrix_chunk_tokens": 1024,
        "_flow_id": "flow-checkpoint-test",
        "_node_id": "node-checkpoint-test",
    }

    with pytest.raises(flow_engine.ModelCallError):
        await flow_engine._exec_samurai(config, source, fixed_context_str=fixed_context)

    result = await flow_engine._exec_samurai(config, source, fixed_context_str=fixed_context)

    assert sum(item.startswith("chunk 1/") for item in calls) == 1
    assert len(__import__("json").loads(result)) >= 2
    checkpoint = (
        tmp_path
        / ".shogun"
        / "agentflow-checkpoints"
        / "flow-checkpoint-test"
        / "node-checkpoint-test.json"
    )
    assert checkpoint.is_file()


@pytest.mark.asyncio
async def test_exhausted_timeout_has_actionable_route_and_context_details(monkeypatch):
    provider = SimpleNamespace(name="Local Ollama", provider_type="ollama")

    async def call_llm(*_args, **_kwargs):
        raise httpx.ReadTimeout("")

    async def record_usage(*_args, **_kwargs):
        return None

    monkeypatch.setattr(flow_engine, "_call_llm", call_llm)
    monkeypatch.setattr(flow_engine, "_record_model_usage", record_usage)

    with pytest.raises(flow_engine.ModelCallError) as captured:
        await flow_engine._call_llm_chain(
            [{"role": "user", "content": "spreadsheet rows"}],
            [(provider, "qwen-test", "http://localhost:11434/v1", {})],
            timeout=120,
            retry_count=0,
            context="AgentFlow Samurai node",
        )

    error = captured.value
    assert str(error) == "AgentFlow Samurai node timed out after 120s using Local Ollama/qwen-test"
    assert error.cause_type == "ReadTimeout"
    assert error.provider == "Local Ollama"
    assert error.model == "qwen-test"
    assert error.input_characters > len("spreadsheet rows")
    assert error.estimated_input_tokens > 0


@pytest.mark.asyncio
async def test_channel_node_injects_predecessor_context(monkeypatch):
    delivered: list[dict] = []

    async def send(message, **kwargs):
        delivered.append({"message": message, **kwargs})
        return {"telegram": {"ok": True, "sent": 1}}

    monkeypatch.setattr(notification_service, "send_channel_message", send)

    result = await flow_engine._exec_channel_send(
        {
            "channel": "telegram",
            "message_template": "Workflow completed:\n{{context}}",
            "telegram_chat_ids": ["123"],
            "message_thread_id": 22,
        },
        "final report",
    )

    assert result == "Message delivered via telegram"
    assert delivered[0]["message"] == "Workflow completed:\nfinal report"
    assert delivered[0]["telegram_chat_ids"] == ["123"]
    assert delivered[0]["telegram_message_thread_id"] == 22


def test_active_skill_context_is_limited_to_model_consumers():
    assert flow_engine._node_uses_active_skill_context("samurai", {}) is True
    assert flow_engine._node_uses_active_skill_context("coding", {"action": "analyze"}) is True
    assert flow_engine._node_uses_active_skill_context("coding", {"action": "write_file"}) is False
    assert flow_engine._node_uses_active_skill_context("mado_browser", {}) is False
    assert flow_engine._node_uses_active_skill_context("email_send", {}) is False
    assert flow_engine._node_uses_active_skill_context("channel_send", {}) is False


@pytest.mark.asyncio
async def test_channel_execution_never_delivers_private_skill_context(monkeypatch):
    delivered: list[str] = []

    async def update_state(*_args, **_kwargs):
        return None

    async def send(message, **_kwargs):
        delivered.append(message)
        return {"telegram": {"ok": True, "sent": 1}}

    monkeypatch.setattr(flow_engine, "_update_node_state", update_state)
    monkeypatch.setattr(notification_service, "send_channel_message", send)

    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="channel_send",
        label="Send morning brief",
        config={"channel": "telegram", "message_template": "{{context}}"},
    )
    predecessor_id = str(uuid.uuid4())
    predecessor = SimpleNamespace(label="Compile AI News Brief")

    result = await flow_engine._execute_single_node(
        run_id=uuid.uuid4(),
        node=node,
        predecessor_outputs={predecessor_id: "The actual morning brief"},
        node_map={predecessor_id: predecessor},
    )

    assert result == "Message delivered via telegram"
    assert delivered == ["[Output from 'Compile AI News Brief']:\nThe actual morning brief"]
    assert "SKILL AWARENESS PROTOCOL" not in delivered[0]


@pytest.mark.asyncio
async def test_extract_node_with_url_navigates_before_reading(monkeypatch, tmp_path):
    from shogun.config import settings

    monkeypatch.setattr(settings, "mado_path", tmp_path / "mado")
    from shogun.services import mado_hardening, mado_service

    calls: list[tuple[str, str | None]] = []

    async def allowed(*_args, **_kwargs):
        return None

    async def posture():
        return {"active_tier": "campaign"}

    async def launched(**_kwargs):
        return {"status": "already_active"}

    async def governed(_session_id, _action_type, operation, **_kwargs):
        return await operation()

    async def navigate(*, session_id, url):
        calls.append(("navigate", url))
        return {"status": "ok", "url": url, "title": "AI News"}

    async def extract(*, session_id, selector, extract_type):
        calls.append(("extract", selector))
        return {"status": "ok", "content": "Headline one\nHeadline two"}

    monkeypatch.setattr(posture_guard, "check_mado_access", allowed)
    monkeypatch.setattr(posture_guard, "get_posture_tool_filter", posture)
    monkeypatch.setattr(posture_guard, "check_mado_browser_mode", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mado_hardening.permission_guard, "check", allowed)
    monkeypatch.setattr(mado_hardening, "governed_action", governed)
    monkeypatch.setattr(mado_hardening.runtime_registry, "register", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(mado_service, "launch_browser", launched)
    monkeypatch.setattr(mado_service, "navigate", navigate)
    monkeypatch.setattr(mado_service, "extract_content", extract)
    monkeypatch.setitem(mado_service._active_contexts, "flow_morning_news", object())

    result = await flow_engine._exec_mado_browser(
        {
            "action": "extract_content",
            "url": "https://example.test/ai",
            "selector": "article",
            "session_name": "morning_news",
        },
        "",
    )

    assert result == "Headline one\nHeadline two"
    assert calls == [("navigate", "https://example.test/ai"), ("extract", "article")]


def test_notification_cursor_only_returns_new_events():
    notification_service._notifications.clear()
    first = notification_service.publish_notification(
        event_type="model.fallback",
        title="Fallback",
        message="First",
    )
    second = notification_service.publish_notification(
        event_type="model.fallback",
        title="Fallback",
        message="Second",
    )

    assert notification_service.list_notifications(first["id"]) == [second]


@pytest.mark.asyncio
async def test_setting_default_routing_profile_clears_previous_default():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: ModelRoutingProfile.__table__.create(sync_connection)
        )

    async with sessions() as session:
        service = ModelRoutingProfileService(session)
        first = await service.create(name="First", rules=[], is_default=True)
        second = await service.create(name="Second", rules=[], is_default=False)
        await service.update(second.id, is_default=True)
        await session.commit()
        await session.refresh(first)
        await session.refresh(second)
        assert first.is_default is False
        assert second.is_default is True

    await engine.dispose()
