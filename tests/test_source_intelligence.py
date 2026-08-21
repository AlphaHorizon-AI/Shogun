"""Registry-driven Source Intelligence remains bounded and fail-closed."""

from __future__ import annotations

import json
from copy import deepcopy
from importlib.resources import files

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.db.base import Base
from shogun.db.models.transformation_profile import (
    RegisteredTransformationProfile,
    TransformationAdapter,
    TransformationProfileVersion,
)
from shogun.schemas.source_intelligence import (
    SemanticClassifierResponse,
    SourceArtifactInput,
    SourceIntelligenceRequest,
)
from shogun.services.private_transformation_profiles import (
    PrivateTransformationProfileService,
)
from shogun.services.source_intelligence import (
    SourceIntelligenceError,
    SourceIntelligenceService,
    SourceProfileAmbiguousError,
    SourceProfileUnknownError,
    summarize_sources,
)
from shogun.services.transformation_profile_registry import profile_content_hash


@pytest_asyncio.fixture
async def source_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[
                    TransformationAdapter.__table__,
                    RegisteredTransformationProfile.__table__,
                    TransformationProfileVersion.__table__,
                ],
            )
        )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()


def _bundled_definition(name: str = "d365_fscm_sales_order_v1") -> dict:
    resource = files("shogun").joinpath("resources", "transformation_profiles", f"{name}.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def _all_bundled_definitions() -> list[dict]:
    root = files("shogun").joinpath("resources", "transformation_profiles")
    definitions: list[dict] = []
    for resource in root.iterdir():
        if resource.name == "catalog_v1.json" or not resource.name.endswith(".json"):
            continue
        payload = json.loads(resource.read_text(encoding="utf-8"))
        if payload.get("resource_type") == "transformation_profile":
            definitions.append(payload)
    return definitions


async def _add_active_profile(session, definition: dict) -> None:
    adapter_id = str(definition["adapter"])
    adapter = await session.get(TransformationAdapter, adapter_id)
    if adapter is None:
        adapter = TransformationAdapter(
            adapter_id=adapter_id,
            display_name=adapter_id,
            status="available",
            implementation="test",
            capabilities=[],
            metadata_json={"version": 2},
        )
        session.add(adapter)
        await session.flush()
    platform = definition.get("platform") or {}
    profile = RegisteredTransformationProfile(
        profile_key=definition["id"],
        display_name=definition.get("title") or definition["id"],
        platform=platform.get("product", "generic"),
        domain=platform.get("family", "document"),
        lifecycle_status="active",
        protected=False,
        bundled=False,
        metadata_json={},
    )
    session.add(profile)
    await session.flush()
    version = TransformationProfileVersion(
        profile_id=profile.id,
        version_number=1,
        status="active",
        adapter_id=adapter_id,
        required_adapter_status="available",
        origin="operator",
        content_hash=profile_content_hash(definition),
        definition=deepcopy(definition),
        validation_report={},
        metadata_json={},
    )
    session.add(version)
    await session.flush()
    profile.active_version_id = version.id
    await session.flush()


def _d365_artifact(*, include_context: bool = True) -> dict:
    artifact = {
        "source_id": "sales-orders",
        "payload": {
            "value": [
                {
                    "dataAreaId": "USMF",
                    "SalesOrderNumber": "SO-1",
                    "SalesOrderLines": [{"LineNumber": 1}],
                }
            ]
        },
    }
    if include_context:
        artifact["context"] = {
            "transport": "odata_v4",
            "object": "SalesOrderHeadersV2",
            "connector": "d365",
        }
    return artifact


def _private_sectioned_profile() -> dict:
    return {
        "id": "tenant_private_schedule_v1",
        "adapter": "sectioned_record_matrix_v1",
        "parameters": {
            "required_source_patterns": [r"(?m)^Record:\s*\S+"],
            "section_pattern": r"(?m)^Record:\s*(?P<section_id>\S+)",
            "section_key_group": "section_id",
            "record_pattern": r"(?m)^Item:\s*(?P<kind>\S+)\s+(?P<value>\S+)$",
            "record_section_key_group": "",
            "row_rules": [{"kind": "record", "columns": {"0": {"group": "value"}}}],
        },
        "model_fallback": False,
    }


def _semantic_response(
    profile_ids: list[str],
    *,
    confidence: float = 0.96,
    classification: str = "classified",
) -> dict:
    return {
        "contract": "shogun.source-classifier.v1",
        "classification": classification,
        "platform_family": "d365",
        "product": "Dynamics 365 Finance and Supply Chain Management",
        "business_object": "sales_order",
        "candidate_profile_ids": profile_ids,
        "specialist_skill": "d365-transformation-specialist",
        "confidence": confidence,
        "evidence": [{"observation": "dataAreaId is present", "source_ids": ["sales-orders"]}],
        "unknowns": [],
    }


@pytest.mark.asyncio
async def test_exact_active_registry_match_is_executable(source_session):
    definition = _bundled_definition()
    await _add_active_profile(source_session, definition)
    service = SourceIntelligenceService(source_session)

    result = await service.inspect({"artifacts": [_d365_artifact()]})

    assert result.outcome == "exact"
    assert result.execution_allowed is True
    assert result.selected_profile is not None
    assert result.selected_profile.profile_id == "d365_fscm_sales_order_v1"
    assert result.specialist_skill == "d365-transformation-specialist"
    assert "definition" not in result.model_dump_json()

    executable = await service.resolve_executable([_d365_artifact()])
    assert executable.definition["id"] == "d365_fscm_sales_order_v1"
    assert executable.evidence["status"] == "active"


@pytest.mark.asyncio
async def test_partial_match_is_unknown_and_fails_closed(source_session):
    await _add_active_profile(source_session, _bundled_definition())
    service = SourceIntelligenceService(source_session)

    result = await service.inspect({"artifacts": [_d365_artifact(include_context=False)]})

    assert result.outcome == "unknown"
    assert result.execution_allowed is False
    assert result.classifier_request is not None
    assert result.classifier_request.allowed_profile_ids == ["d365_fscm_sales_order_v1"]
    with pytest.raises(SourceProfileUnknownError) as captured:
        await service.resolve_executable([_d365_artifact(include_context=False)])
    assert captured.value.result.outcome == "unknown"


@pytest.mark.asyncio
async def test_unknown_source_classifier_can_consider_the_installed_public_catalogue(
    source_session,
):
    d365 = _bundled_definition()
    business_central = _bundled_definition("business_central_sales_order_v1")
    await _add_active_profile(source_session, d365)
    await _add_active_profile(source_session, business_central)

    result = await SourceIntelligenceService(source_session).inspect(
        {
            "artifacts": [
                {
                    "source_id": "opaque-export",
                    "text": "Unlabeled enterprise order export with unfamiliar headers",
                }
            ]
        }
    )

    assert result.outcome == "unknown"
    assert result.classifier_request is not None
    assert set(result.classifier_request.allowed_profile_ids) == {
        "d365_fscm_sales_order_v1",
        "business_central_sales_order_v1",
    }
    assert {
        candidate.specialist_skill for candidate in result.classifier_request.candidates
    } == {
        "d365-transformation-specialist",
        "business-central-transformation-specialist",
    }


@pytest.mark.asyncio
async def test_classifier_contract_indexes_every_bundled_source_profile():
    definitions = _all_bundled_definitions()

    class BundledRegistry:
        async def list_active_definitions(self):
            return [
                {
                    "definition": definition,
                    "registry_evidence": {
                        "profile_id": definition["id"],
                        "version": int(definition.get("version") or 1),
                        "content_hash": profile_content_hash(definition),
                        "status": "active",
                        "adapter_id": definition["adapter"],
                        "adapter_status": "available",
                        "version_id": f"version-{index}",
                    },
                    "profile_metadata": {
                        "platform": definition.get("platform", {}).get("product", "generic"),
                        "domain": definition.get("platform", {}).get("family", "enterprise"),
                    },
                }
                for index, definition in enumerate(definitions, start=1)
            ]

    result = await SourceIntelligenceService(
        None,
        registry_service=BundledRegistry(),
    ).inspect(
        {
            "artifacts": [
                {
                    "source_id": "unknown-enterprise-source",
                    "text": "Opaque enterprise export without stable vendor labels",
                }
            ]
        }
    )

    assert len(definitions) == 86
    assert result.classifier_request is not None
    assert len(result.classifier_request.allowed_profile_ids) == len(definitions)
    assert set(result.classifier_request.allowed_profile_ids) == {
        definition["id"] for definition in definitions
    }
    assert len(result.classifier_request.model_dump_json().encode("utf-8")) < 256_000


@pytest.mark.asyncio
async def test_two_exact_profiles_are_ambiguous(source_session):
    original = _bundled_definition()
    duplicate = deepcopy(original)
    duplicate["id"] = "tenant_d365_sales_order_v1"
    duplicate["title"] = "Tenant D365 sales order"
    await _add_active_profile(source_session, original)
    await _add_active_profile(source_session, duplicate)
    service = SourceIntelligenceService(source_session)

    result = await service.inspect({"artifacts": [_d365_artifact()]})

    assert result.outcome == "ambiguous"
    assert result.execution_allowed is False
    assert {item.profile_id for item in result.candidates} == {
        "d365_fscm_sales_order_v1",
        "tenant_d365_sales_order_v1",
    }
    with pytest.raises(SourceProfileAmbiguousError):
        await service.resolve_executable([_d365_artifact()])


@pytest.mark.asyncio
async def test_private_match_stays_local_and_never_enters_classifier_allow_list(source_session):
    await _add_active_profile(source_session, _bundled_definition())
    private = PrivateTransformationProfileService().export_profile(
        _private_sectioned_profile()
    )["profile_reference"]
    service = SourceIntelligenceService(source_session)

    exact = await service.inspect(
        {
            "artifacts": [{"source_id": "private", "text": "Record: A\nItem: row 1"}],
            "private_profiles": [private],
        }
    )
    assert exact.outcome == "exact"
    assert exact.selected_profile is not None
    assert exact.selected_profile.profile_source == "private"
    serialized = exact.model_dump_json()
    assert "required_source_patterns" not in serialized
    assert "(?m)" not in serialized

    unknown = await service.inspect(
        {
            "artifacts": [{"source_id": "unknown", "text": "unrecognized data"}],
            "private_profiles": [private],
        }
    )
    assert unknown.classifier_request is not None
    assert "tenant_private_schedule_v1" not in unknown.classifier_request.allowed_profile_ids
    assert all(
        item.profile_id != "tenant_private_schedule_v1"
        for item in unknown.classifier_request.candidates
    )


@pytest.mark.asyncio
async def test_private_exact_match_routes_by_source_when_profile_id_is_opaque(source_session):
    private = PrivateTransformationProfileService().export_profile(
        _private_sectioned_profile()
    )["profile_reference"]

    result = await SourceIntelligenceService(source_session).inspect(
        {
            "artifacts": [
                {
                    "source_id": "private-sap-report",
                    "text": "SAP S/4HANA material planning\nRecord: A\nItem: row 1",
                }
            ],
            "private_profiles": [private],
        }
    )

    assert result.outcome == "exact"
    assert result.specialist_skill == "sap-transformation-specialist"
    assert result.selected_profile is not None
    assert result.selected_profile.specialist_skill == "sap-transformation-specialist"


@pytest.mark.asyncio
async def test_private_public_ambiguity_cannot_be_semantically_resolved(source_session):
    public = _bundled_definition()
    public["selection"] = {
        "positive_fingerprints": ["field:Record"],
        "negative_fingerprints": [],
    }
    await _add_active_profile(source_session, public)
    private = PrivateTransformationProfileService().export_profile(
        _private_sectioned_profile()
    )["profile_reference"]

    result = await SourceIntelligenceService(source_session).inspect(
        {
            "artifacts": [
                {"source_id": "document", "text": "Record: A\nItem: row 1"},
                {"source_id": "payload", "payload": {"Record": "A"}},
            ],
            "private_profiles": [private],
        }
    )

    assert result.outcome == "ambiguous"
    assert {item.profile_source for item in result.candidates} == {"registry", "private"}
    assert result.classifier_request is not None
    assert result.classifier_request.allowed_profile_ids == []
    assert result.classifier_request.candidates == []


@pytest.mark.asyncio
async def test_semantic_nomination_is_advisory_and_constrained(source_session):
    definition = _bundled_definition()
    await _add_active_profile(source_session, definition)
    service = SourceIntelligenceService(source_session)
    unknown = await service.inspect({"artifacts": [_d365_artifact(include_context=False)]})
    request = unknown.classifier_request
    assert request is not None

    nomination = await service.resolve_semantic_nomination(
        request,
        _semantic_response(["d365_fscm_sales_order_v1"]),
    )
    assert nomination.definition["id"] == "d365_fscm_sales_order_v1"
    assert nomination.execution_allowed is False
    assert nomination.requires_deterministic_validation is True
    assert nomination.evidence["selection_authority"] == "semantic_advisory"
    assert nomination.evidence["execution_allowed"] is False

    with pytest.raises(SourceIntelligenceError, match="outside the request allow-list"):
        await service.resolve_semantic_nomination(
            request,
            _semantic_response(["not_installed_v1"]),
        )
    with pytest.raises(SourceIntelligenceError, match="below the required threshold"):
        await service.resolve_semantic_nomination(
            request,
            _semantic_response(["d365_fscm_sales_order_v1"], confidence=0.5),
        )
    with pytest.raises(SourceIntelligenceError, match="exactly one"):
        await service.resolve_semantic_nomination(request, _semantic_response([]))

    expanded_request = request.model_copy(
        update={
            "allowed_profile_ids": [
                "d365_fscm_sales_order_v1",
                "another_allowed_profile_v1",
            ]
        }
    )
    with pytest.raises(SourceIntelligenceError, match="exactly one"):
        await service.resolve_semantic_nomination(
            expanded_request,
            _semantic_response(
                ["d365_fscm_sales_order_v1", "another_allowed_profile_v1"]
            ),
        )


def test_semantic_response_cannot_carry_profile_mechanics():
    payload = _semantic_response(["d365_fscm_sales_order_v1"])
    payload["definition"] = {"adapter": "arbitrary"}
    with pytest.raises(ValidationError):
        SemanticClassifierResponse.model_validate(payload)


def test_large_pdf_text_is_inspected_but_classifier_summary_remains_bounded():
    page = "SAP S/4HANA material plan\nRecord: A\nItem: row 1\n"
    text = page * 12_000
    assert len(text) > 536_000
    request = SourceIntelligenceRequest(
        artifacts=[
            SourceArtifactInput(
                source_id="large-pdf",
                text=text,
                context={"content_type": "application/pdf", "file_name": "input.pdf"},
            )
        ]
    )

    summary = summarize_sources(request.artifacts)
    serialized = summary.model_dump_json()

    assert summary.total_bytes == len(text.encode("utf-8"))
    assert sum(len(item) for item in summary.artifacts[0].sample_excerpts) <= 3_000
    assert len(serialized) < 20_000
    assert text not in serialized


@pytest.mark.asyncio
async def test_valid_private_source_pattern_matches_large_pdf_tail(source_session):
    private = PrivateTransformationProfileService().export_profile(
        _private_sectioned_profile()
    )["profile_reference"]
    text = ("unrelated line\n" * 45_000) + "Record: A\nItem: row 1\n"
    assert len(text) > 536_000

    result = await SourceIntelligenceService(source_session).inspect(
        {
            "artifacts": [
                {
                    "source_id": "large-private-pdf",
                    "text": text,
                    "context": {
                        "content_type": "application/pdf",
                        "file_name": "input.pdf",
                    },
                }
            ],
            "private_profiles": [private],
        }
    )

    assert result.outcome == "exact"
    assert result.execution_allowed is True
    assert result.selected_profile is not None
    assert result.selected_profile.profile_source == "private"
