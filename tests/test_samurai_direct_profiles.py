from __future__ import annotations

import uuid
from copy import deepcopy
from types import SimpleNamespace

import pytest

from shogun.engine import flow_engine
from shogun.mapping.errors import MappingSchemaError
from shogun.schemas.agent_flow import AgentFlowNodeCreate
from shogun.schemas.source_intelligence import (
    SemanticClassificationEvidence,
    SemanticClassifierRequest,
    SemanticClassifierResponse,
    SourceArtifactInput,
    SourceIntelligenceResult,
)
from shogun.services.private_transformation_profiles import PrivateTransformationProfileService
from shogun.services.source_intelligence import (
    SourceIntelligenceService,
    SourceProfileUnknownError,
    summarize_sources,
)
from shogun.services.transformation_profile_registry import profile_content_hash

PROFILE = {
    "id": "synthetic_direct_report_v1",
    "adapter": "sectioned_record_matrix_v1",
    "parameters": {
        "required_source_patterns": [r"(?m)^Record: "],
        "section_pattern": r"(?m)^Record: (?P<section_id>\S+)",
    },
}

CANONICAL_PROFILE = {
    "id": "synthetic_canonical_orders_v1",
    "adapter": "canonical_entity_map_v1",
    "parameters": {},
}


def _pinned_reference(definition: dict | None = None) -> dict:
    definition = definition or PROFILE
    return {
        "id": definition["id"],
        "adapter": definition["adapter"],
        "registry_version": 3,
        "content_hash": profile_content_hash(definition),
    }


def _registry_evidence(definition: dict | None = None) -> dict:
    definition = definition or PROFILE
    return {
        "profile_id": definition["id"],
        "adapter_id": definition["adapter"],
        "version": 3,
        "content_hash": profile_content_hash(definition),
        "status": "active",
        "adapter_status": "available",
        "version_id": "version-3",
    }


def test_samurai_schema_normalizes_direct_and_general_modes():
    general = AgentFlowNodeCreate(
        node_type="samurai",
        config={"task_description": "Summarize the input"},
    )
    direct = AgentFlowNodeCreate(
        node_type="samurai",
        config={
            "task_description": "Transform the input",
            "transformation_mode": "profile",
            "transformation_profile": _pinned_reference(),
        },
    )

    assert general.config["transformation_mode"] == "general"
    assert "transformation_profile" not in general.config
    assert direct.config["transformation_mode"] == "profile"
    assert direct.config["transformation_profile"]["registry_version"] == 3
    assert direct.config["transformation_profile"]["content_hash"] == profile_content_hash(PROFILE)


@pytest.mark.parametrize("mode", ["general", "auto"])
def test_samurai_schema_rejects_profile_in_non_profile_mode(mode):
    with pytest.raises(ValueError, match="only allowed"):
        AgentFlowNodeCreate(
            node_type="samurai",
            config={
                "task_description": "Transform",
                "transformation_mode": mode,
                "transformation_profile": _pinned_reference(),
            },
        )


def test_samurai_schema_requires_profile_in_profile_mode():
    with pytest.raises(ValueError, match="requires a transformation_profile"):
        AgentFlowNodeCreate(
            node_type="samurai",
            config={"task_description": "Transform", "transformation_mode": "profile"},
        )


@pytest.mark.asyncio
async def test_direct_registry_profile_fails_closed_on_wrong_hash(monkeypatch):
    wrong_pin = {**_pinned_reference(), "content_hash": "ab" * 32}

    async def resolve(_profile):
        return deepcopy(PROFILE), _registry_evidence()

    monkeypatch.setattr(flow_engine, "_resolve_registered_enterprise_profile", resolve)

    with pytest.raises(MappingSchemaError, match="version/hash pin"):
        await flow_engine._resolve_direct_samurai_profile(wrong_pin)


@pytest.mark.asyncio
async def test_samurai_receives_direct_profile_without_mapping_node(monkeypatch):
    captured: dict[str, object] = {}

    async def update_state(*_args, **_kwargs):
        return None

    async def resolve(_profile):
        return deepcopy(PROFILE), {
            **_registry_evidence(),
            "selection_mode": "profile",
            "profile_source": "registry",
        }

    async def execute_samurai(config, context, _governance, **kwargs):
        captured["profiles"] = config.get("_transformation_profiles")
        captured["evidence"] = config.get("_transformation_profile_evidence")
        captured["context"] = context
        captured["fixed"] = kwargs.get("fixed_context_str")
        captured["artifacts"] = config.get("_input_artifacts")
        return "deterministic result"

    monkeypatch.setattr(flow_engine, "_update_node_state", update_state)
    monkeypatch.setattr(flow_engine, "_resolve_direct_samurai_profile", resolve)
    monkeypatch.setattr(flow_engine, "_exec_samurai", execute_samurai)
    monkeypatch.setattr(flow_engine, "_finalize_node_skills", update_state)
    monkeypatch.setattr(flow_engine, "_node_uses_active_skill_context", lambda *_args: False)

    source_id = str(uuid.uuid4())
    template_id = str(uuid.uuid4())
    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="samurai",
        label="Direct deterministic transform",
        config={
            "task_description": "Transform every record",
            "transformation_mode": "profile",
            "transformation_profile": _pinned_reference(),
        },
    )
    template = {
        "__shogun_file_template__": True,
        "template_path": "Templates/output.xlsx",
        "format": "xlsx",
        "manifest": {"logical_columns": 2},
    }
    result = await flow_engine._execute_single_node(
        uuid.uuid4(),
        node,
        {source_id: "Record: A\nsource row", template_id: template},
        {
            source_id: SimpleNamespace(
                id=source_id,
                label="Input PDF",
                node_type="office",
                config={"action": "pdf_read"},
            ),
            template_id: SimpleNamespace(
                id=template_id,
                label="Output template",
                node_type="file_template",
                config={},
            ),
        },
    )

    assert result == "deterministic result"
    assert captured["profiles"] == [PROFILE]
    assert captured["evidence"] == [
        {
            **_registry_evidence(),
            "selection_mode": "profile",
            "profile_source": "registry",
        }
    ]
    assert "Record: A" in str(captured["context"])
    assert "synthetic_direct_report_v1" not in str(captured["context"])
    assert "synthetic_direct_report_v1" not in str(captured["artifacts"])
    assert "FILE TEMPLATE CONTRACT" in str(captured["fixed"])


@pytest.mark.asyncio
async def test_direct_profile_rejects_wrong_runtime_source(monkeypatch):
    async def update_state(*_args, **_kwargs):
        return None

    async def resolve(_profile):
        return deepcopy(PROFILE), {
            **_registry_evidence(),
            "selection_mode": "profile",
            "profile_source": "registry",
        }

    async def unexpected_route(*_args, **_kwargs):
        raise AssertionError("a failed direct profile must not route to a model")

    monkeypatch.setattr(flow_engine, "_update_node_state", update_state)
    monkeypatch.setattr(flow_engine, "_resolve_direct_samurai_profile", resolve)
    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", unexpected_route)
    monkeypatch.setattr(flow_engine, "_finalize_node_skills", update_state)
    monkeypatch.setattr(flow_engine, "_node_uses_active_skill_context", lambda *_args: False)

    source_id = str(uuid.uuid4())
    template_id = str(uuid.uuid4())
    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="samurai",
        label="Direct deterministic transform",
        config={
            "task_description": "Transform every record",
            "transformation_mode": "profile",
            "transformation_profile": _pinned_reference(),
        },
    )

    with pytest.raises(ValueError, match="Runtime source 'Wrong PDF' does not match"):
        await flow_engine._execute_single_node(
            uuid.uuid4(),
            node,
            {
                source_id: "Object: A\nsource row",
                template_id: {
                    "__shogun_file_template__": True,
                    "format": "xlsx",
                    "manifest": {"logical_columns": 2},
                },
            },
            {
                source_id: SimpleNamespace(
                    id=source_id,
                    label="Wrong PDF",
                    node_type="office",
                    config={"action": "pdf_read"},
                ),
                template_id: SimpleNamespace(
                    id=template_id,
                    label="Template",
                    node_type="file_template",
                    config={},
                ),
            },
            downstream_contracts=[{"action": "excel_create", "format": "xlsx"}],
        )


@pytest.mark.asyncio
async def test_direct_profile_conflicts_with_upstream_contract(monkeypatch):
    async def update_state(*_args, **_kwargs):
        return None

    monkeypatch.setattr(flow_engine, "_update_node_state", update_state)
    monkeypatch.setattr(
        flow_engine,
        "_trusted_contract_profile_from_carrier",
        lambda *_args, **_kwargs: deepcopy(PROFILE),
    )

    mapping_id = str(uuid.uuid4())
    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="samurai",
        label="Ambiguous transform",
        config={
            "task_description": "Transform",
            "transformation_mode": "profile",
            "transformation_profile": _pinned_reference(),
        },
    )
    mapping_node = SimpleNamespace(
        label="Legacy contract",
        node_type="mapping_rpa",
        config={
            "execution_mode": "contract",
            "transformation_profile": PROFILE,
        },
    )

    with pytest.raises(ValueError, match="conflicts with an upstream"):
        await flow_engine._execute_single_node(
            uuid.uuid4(),
            node,
            {
                mapping_id: {
                    "status": "SUCCESS",
                    "registry_evidence": _registry_evidence(),
                }
            },
            {mapping_id: mapping_node},
        )


@pytest.mark.asyncio
async def test_general_mode_remains_on_generic_samurai_path(monkeypatch):
    captured: dict[str, object] = {}

    async def update_state(*_args, **_kwargs):
        return None

    async def execute_samurai(config, context, _governance, **_kwargs):
        captured["profiles"] = config.get("_transformation_profiles")
        captured["context"] = context
        return "model result"

    async def unexpected_direct_resolution(*_args, **_kwargs):
        raise AssertionError("general mode must not resolve a transformation profile")

    monkeypatch.setattr(flow_engine, "_update_node_state", update_state)
    monkeypatch.setattr(flow_engine, "_exec_samurai", execute_samurai)
    monkeypatch.setattr(flow_engine, "_resolve_direct_samurai_profile", unexpected_direct_resolution)
    monkeypatch.setattr(flow_engine, "_finalize_node_skills", update_state)
    monkeypatch.setattr(flow_engine, "_node_uses_active_skill_context", lambda *_args: False)

    source_id = str(uuid.uuid4())
    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="samurai",
        label="Generic Samurai",
        config={"task_description": "Summarize", "transformation_mode": "general"},
    )
    result = await flow_engine._execute_single_node(
        uuid.uuid4(),
        node,
        {source_id: "Unknown input structure"},
        {
            source_id: SimpleNamespace(
                id=source_id,
                label="Unknown input",
                node_type="office",
                config={"action": "pdf_read"},
            )
        },
    )

    assert result == "model result"
    assert captured["profiles"] == []
    assert captured["context"] == "[Output from 'Unknown input']:\nUnknown input structure"


@pytest.mark.asyncio
async def test_transform_mapping_profile_metadata_never_activates_samurai(monkeypatch):
    captured: dict[str, object] = {}

    async def no_op(*_args, **_kwargs):
        return None

    async def execute_samurai(config, context, _governance, **_kwargs):
        captured["profiles"] = config.get("_transformation_profiles")
        captured["evidence"] = config.get("_transformation_profile_evidence")
        captured["context"] = context
        return "generic result"

    monkeypatch.setattr(flow_engine, "_update_node_state", no_op)
    monkeypatch.setattr(flow_engine, "_exec_samurai", execute_samurai)
    monkeypatch.setattr(flow_engine, "_finalize_node_skills", no_op)
    monkeypatch.setattr(flow_engine, "_node_uses_active_skill_context", lambda *_args: False)

    mapping_id = str(uuid.uuid4())
    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="samurai",
        label="Generic Samurai",
        config={"task_description": "Summarize", "transformation_mode": "general"},
    )
    mapping_node = SimpleNamespace(
        id=mapping_id,
        label="Ordinary mapping",
        node_type="mapping_rpa",
        config={
            "execution_mode": "transform",
            "mappings": [{"source": "name", "target": "A"}],
            "transformation_profile": PROFILE,
        },
    )

    result = await flow_engine._execute_single_node(
        uuid.uuid4(),
        node,
        {mapping_id: {"status": "SUCCESS", "rows": [["Acme"]]}},
        {mapping_id: mapping_node},
    )

    assert result == "generic result"
    assert captured["profiles"] == []
    assert captured["evidence"] == []
    assert "Acme" in str(captured["context"])


@pytest.mark.asyncio
async def test_canonical_transform_metadata_stays_generic_without_evidence_indexing(monkeypatch):
    async def no_op(*_args, **_kwargs):
        return None

    async def execute_samurai(config, _context, _governance, **_kwargs):
        assert config.get("_transformation_profiles") == []
        assert config.get("_transformation_profile_evidence") == []
        return "generic result"

    async def unexpected_enterprise_execution(*_args, **_kwargs):
        raise AssertionError("transform-mode metadata must not execute a canonical profile")

    monkeypatch.setattr(flow_engine, "_update_node_state", no_op)
    monkeypatch.setattr(flow_engine, "_exec_samurai", execute_samurai)
    monkeypatch.setattr(
        flow_engine,
        "_exec_samurai_enterprise_profile",
        unexpected_enterprise_execution,
    )
    monkeypatch.setattr(flow_engine, "_finalize_node_skills", no_op)
    monkeypatch.setattr(flow_engine, "_node_uses_active_skill_context", lambda *_args: False)

    mapping_id = str(uuid.uuid4())
    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="samurai",
        label="Generic Samurai",
        config={"task_description": "Summarize", "transformation_mode": "general"},
    )
    mapping_node = SimpleNamespace(
        id=mapping_id,
        label="Ordinary mapping",
        node_type="mapping_rpa",
        config={
            "execution_mode": "transform",
            "mappings": [{"source": "name", "target": "A"}],
            "transformation_profile": CANONICAL_PROFILE,
        },
    )

    result = await flow_engine._execute_single_node(
        uuid.uuid4(),
        node,
        {mapping_id: {"status": "SUCCESS", "rows": [["Acme"]]}},
        {mapping_id: mapping_node},
    )

    assert result == "generic result"


@pytest.mark.asyncio
async def test_direct_profile_activation_fails_before_execution_without_trusted_evidence(monkeypatch):
    async def no_op(*_args, **_kwargs):
        return None

    async def resolve_without_evidence(_profile):
        return deepcopy(CANONICAL_PROFILE), {}

    async def unexpected_execution(*_args, **_kwargs):
        raise AssertionError("a profile without evidence must never execute")

    monkeypatch.setattr(flow_engine, "_update_node_state", no_op)
    monkeypatch.setattr(flow_engine, "_resolve_direct_samurai_profile", resolve_without_evidence)
    monkeypatch.setattr(flow_engine, "_exec_samurai", unexpected_execution)
    monkeypatch.setattr(flow_engine, "_exec_samurai_enterprise_profile", unexpected_execution)
    monkeypatch.setattr(flow_engine, "_finalize_node_skills", no_op)
    monkeypatch.setattr(flow_engine, "_node_uses_active_skill_context", lambda *_args: False)

    source_id = str(uuid.uuid4())
    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="samurai",
        label="Pinned canonical transform",
        config={
            "task_description": "Transform",
            "transformation_mode": "profile",
            "transformation_profile": _pinned_reference(CANONICAL_PROFILE),
        },
    )

    with pytest.raises(ValueError, match="requires trusted registry or private-file evidence"):
        await flow_engine._execute_single_node(
            uuid.uuid4(),
            node,
            {source_id: {"orders": [{"id": "SO-1"}]}},
            {
                source_id: SimpleNamespace(
                    id=source_id,
                    label="Orders",
                    node_type="input",
                    config={"source_transport": "api"},
                )
            },
        )


@pytest.mark.asyncio
async def test_source_semantic_classifier_uses_registered_governed_task_without_legacy_fallback(
    monkeypatch,
):
    from shogun.services import model_router

    provider_id = uuid.uuid4()
    provider = SimpleNamespace(
        id=provider_id,
        name="Governed classifier",
        provider_type="ollama",
        status="connected",
        base_url="http://127.0.0.1:11434/v1",
        config={"model": "classifier-model"},
    )
    routed_task_types: list[str | None] = []

    class FakeSession:
        async def get(self, _model, requested_provider_id):
            assert requested_provider_id == provider_id
            return provider

        async def commit(self):
            return None

    class FakeSessionContext:
        async def __aenter__(self):
            return FakeSession()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class GovernedRouter:
        def __init__(self, _session):
            pass

        async def route(self, request):
            routed_task_types.append(request.task_type)
            return SimpleNamespace(
                selected=SimpleNamespace(
                    provider_id=provider_id,
                    model_id="classifier-model",
                ),
                fallbacks=[],
                payload={"active_profile": "governed"},
            )

    async def forbidden_legacy_chain(*_args, **_kwargs):
        raise AssertionError("a valid governed classification route must not use legacy fallback")

    async def classify(*_args, **_kwargs):
        return SemanticClassifierResponse(
            classification="unknown",
            platform_family="unknown",
            candidate_profile_ids=[],
            specialist_skill="enterprise-transformation-architect",
            confidence=0.0,
            evidence=[],
            unknowns=["Insufficient evidence"],
        ).model_dump_json()

    summary = summarize_sources(
        [SourceArtifactInput(source_id="source-1", text="unknown source")]
    )
    request = SemanticClassifierRequest(
        summary=summary,
        candidates=[],
        allowed_profile_ids=[],
        allowed_specialist_skills=["enterprise-transformation-architect"],
    )

    monkeypatch.setattr(model_router, "ModelRoutingService", GovernedRouter)
    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: FakeSessionContext())
    monkeypatch.setattr(flow_engine, "_resolve_llm_chain", forbidden_legacy_chain)
    monkeypatch.setattr(flow_engine, "_call_llm_chain", classify)

    response = await flow_engine._run_source_semantic_classifier(
        request,
        config={},
        governance_context={},
    )

    assert response.classification == "unknown"
    assert routed_task_types == ["classification"]


@pytest.mark.asyncio
async def test_private_auto_exact_match_preserves_marker_beyond_536k():
    definition = {
        "id": "private_large_document_v1",
        "adapter": "sectioned_record_matrix_v1",
        "parameters": {
            "required_source_patterns": [r"(?m)^PRIVATE-TAIL-MARKER$"],
            "section_pattern": r"(?m)^Record: (?P<section_id>\S+)",
            "record_pattern": r"(?m)^Record: (?P<id>\S+) (?P<quantity>\d+)$",
            "record_section_key_group": "id",
            "row_rules": [
                {
                    "kind": "record",
                    "columns": {
                        "0": {"group": "id"},
                        "1": {
                            "group": "quantity",
                            "value_type": "localized_number",
                        },
                    },
                }
            ],
        },
    }
    private_reference = PrivateTransformationProfileService().export_profile(
        definition,
        execution_mode="contract",
    )["profile_reference"]
    source_text = ("ordinary filler line\n" * 30_000) + (
        "PRIVATE-TAIL-MARKER\nRecord: ITEM-A 12\n"
    )
    assert len(source_text) > 536 * 1024
    artifacts = flow_engine._source_intelligence_artifacts(
        [
            {
                "source_id": "pdf-1",
                "label": "Large private PDF",
                "raw_output": source_text,
                "text_output": source_text,
                "context": {"transport": "pdf", "content_type": "pdf"},
            }
        ]
    )
    assert len(artifacts[0]["text"]) == len(source_text)

    class EmptyRegistry:
        async def list_active_definitions(self):
            return []

    resolved = await SourceIntelligenceService(
        None,
        registry_service=EmptyRegistry(),
    ).resolve_executable(
        artifacts,
        private_profiles=[private_reference],
    )

    assert resolved.definition == definition
    assert resolved.resolution.outcome == "exact"
    assert resolved.resolution.selected_profile is not None
    assert resolved.resolution.selected_profile.profile_source == "private"


@pytest.mark.asyncio
async def test_open_set_unknown_classifies_platform_then_stops_without_execution(monkeypatch):
    artifacts = flow_engine._source_intelligence_artifacts(
        [
            {
                "source_id": "source-1",
                "label": "Unrecognized ERP export",
                "raw_output": "Unfamiliar invoice structure",
                "text_output": "Unfamiliar invoice structure",
                "context": {"transport": "pdf"},
            }
        ]
    )
    summary = summarize_sources(
        [SourceArtifactInput.model_validate(artifact) for artifact in artifacts]
    )
    classifier_request = SemanticClassifierRequest(
        summary=summary,
        candidates=[],
        allowed_profile_ids=[],
        allowed_specialist_skills=["oracle-fusion-transformation-specialist"],
    )
    initial_result = SourceIntelligenceResult(
        outcome="unknown",
        execution_allowed=False,
        summary=summary,
        candidates=[],
        specialist_skill="enterprise-transformation-architect",
        classifier_request=classifier_request,
    )
    nomination_called = False

    class FakeSourceIntelligenceService:
        def __init__(self, _session):
            pass

        async def resolve_executable(self, *_args, **_kwargs):
            raise SourceProfileUnknownError(initial_result)

        async def resolve_semantic_nomination(self, *_args, **_kwargs):
            nonlocal nomination_called
            nomination_called = True
            raise AssertionError("zero-candidate discovery must not nominate or execute a profile")

    async def classify(*_args, **_kwargs):
        return SemanticClassifierResponse(
            classification="classified",
            platform_family="oracle",
            product="Oracle Fusion ERP",
            business_object="AP invoice",
            candidate_profile_ids=[],
            specialist_skill="oracle-fusion-transformation-specialist",
            confidence=0.94,
            evidence=[
                SemanticClassificationEvidence(
                    observation="Oracle invoice vocabulary and field grouping",
                    source_ids=["source-1"],
                )
            ],
            unknowns=["No installed exact source-layout profile"],
        )

    monkeypatch.setattr(
        "shogun.services.source_intelligence.SourceIntelligenceService",
        FakeSourceIntelligenceService,
    )
    monkeypatch.setattr(flow_engine, "_run_source_semantic_classifier", classify)

    with pytest.raises(flow_engine.SourceIntelligenceResolutionError) as caught:
        await flow_engine._resolve_auto_samurai_profile(
            source_inputs=[
                {
                    "source_id": "source-1",
                    "label": "Unrecognized ERP export",
                    "raw_output": "Unfamiliar invoice structure",
                    "text_output": "Unfamiliar invoice structure",
                    "context": {"transport": "pdf"},
                }
            ],
            private_profiles=[],
            config={},
            governance_context={},
        )

    assert nomination_called is False
    assert "no single installed profile" in str(caught.value)
    semantic = caught.value.source_intelligence["semantic_classification"]
    assert semantic["platform_family"] == "oracle"
    assert semantic["specialist_skill"] == "oracle-fusion-transformation-specialist"
    assert semantic["candidate_profile_ids"] == []
