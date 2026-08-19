"""Versioned, fail-closed transformation profile registry tests."""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.db.base import Base
from shogun.db.models.transformation_profile import (
    RegisteredTransformationProfile,
    TransformationAdapter,
    TransformationProfileVersion,
)
from shogun.schemas.transformation_profile import (
    TransformationProfileCandidateCreate,
    TransformationProfileValidationRequest,
)
from shogun.services.transformation_profile_registry import (
    ProtectedTransformationProfileError,
    TransformationAdapterUnavailableError,
    TransformationProfileLifecycleError,
    TransformationProfileRegistryService,
    discover_bundled_profile_manifests,
    profile_content_hash,
)


@pytest_asyncio.fixture
async def registry_session():
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


def _canonical_manifest(profile_id: str = "test_customer_v1", *, adapter: str = "canonical_entity_map_v1"):
    return {
        "resource_type": "transformation_profile",
        "manifest_version": "1.0",
        "id": profile_id,
        "version": 1,
        "lifecycle": "candidate",
        "title": "Test customer",
        "description": "Executable validation fixture profile.",
        "profile_kind": "canonical_ingress",
        "adapter": adapter,
        "parameters": {},
        "platform": {"vendor": "Test", "product": "Test ERP", "family": "erp"},
        "source": {"transport": "rest", "object": "customers", "record_shape": "entity"},
        "canonical_contract": {"id": "customer_master", "version": 1, "record_kind": "customer"},
        "identity": {
            "source_key": ["id"],
            "canonical_key": ["customer_id"],
            "conflict_policy": "error",
        },
        "field_map": [
            {
                "source": "id",
                "target": "customer_id",
                "type": "string",
                "required": True,
                "transforms": ["trim"],
            }
        ],
        "invariants": [
            {"id": "identity", "rule": "required_nonempty", "fields": ["customer_id"]}
        ],
        "privacy": {
            "classification": "internal",
            "pii_fields": [],
            "secret_fields": [],
            "retention": "flow_policy",
        },
        "adapter_requirements": {
            "adapter": adapter,
            "minimum_version": 1,
            "status": "available",
            "capabilities": ["field_mapping"],
            "fail_closed": True,
        },
        "selection": {"positive_fingerprints": [], "negative_fingerprints": []},
        "governance": {
            "minimum_positive_fixtures": 1,
            "minimum_negative_fixtures": 1,
        },
    }


def _candidate_body(profile_id: str = "test_customer_v1", *, adapter: str = "canonical_entity_map_v1"):
    definition = _canonical_manifest(profile_id, adapter=adapter)
    return TransformationProfileCandidateCreate(
        profile_id=profile_id,
        display_name="Test customer",
        platform="Test ERP",
        domain="erp",
        adapter_id=adapter,
        definition=definition,
    )


def _validation_evidence(*, negative_payload=None):
    return TransformationProfileValidationRequest.model_validate(
        {
            "positive_fixtures": [
                {
                    "name": "valid customer",
                    "payload": {"id": " C-1 "},
                    "expected_record_count": 1,
                    "expected_contract_id": "customer_master",
                    "expected_record_kind": "customer",
                    "expected_headers": ["customer_id"],
                    "expected_records": [{"customer_id": "C-1"}],
                }
            ],
            "negative_fixtures": [
                {
                    "name": "missing identity",
                    "payload": {} if negative_payload is None else negative_payload,
                    "expected_error_code": "VALIDATION_FAILED",
                }
            ],
            "actor": "skillopt",
        }
    )


def test_resource_discovery_skips_catalog_and_normalizes_bundled_provenance():
    descriptors = discover_bundled_profile_manifests()
    ids = [item.profile_id for item in descriptors]

    assert len(ids) >= 80
    assert len(ids) == len(set(ids))
    assert "enterprise_transformation_profiles_v1" not in ids
    assert "business_central_customer_master_v1" in ids
    assert "d365_fscm_sales_order_v1" in ids
    assert "salesforce_opportunity_pipeline_v1" in ids
    assert "oracle_fusion_purchase_order_v1" in ids
    assert "netsuite_sales_order_v1" in ids
    assert "ifs_cloud_work_order_v1" in ids
    assert "epicor_kinetic_work_order_v1" in ids
    assert "servicenow_incident_v1" in ids
    assert "hubspot_deal_v1" in ids
    assert "workday_worker_v1" in ids
    sap = next(item for item in descriptors if item.profile_id == "ks_lbp_disposition_v2")
    assert sap.lifecycle == "active"
    assert sap.adapter_id == "sectioned_record_matrix_v1"
    assert all(item.lifecycle == "candidate" for item in descriptors if item is not sap)


@pytest.mark.asyncio
async def test_bundled_sync_is_idempotent_protected_and_fail_closed(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    first = await service.sync_bundled_profiles()
    await registry_session.commit()
    second = await service.sync_bundled_profiles()

    assert first["discovered"] >= 80
    assert first["profiles_created"] == first["discovered"]
    assert first["activated"] == 1
    assert second["profiles_created"] == 0
    assert second["versions_created"] == 0
    count = await registry_session.scalar(select(func.count(RegisteredTransformationProfile.id)))
    version_count = await registry_session.scalar(select(func.count(TransformationProfileVersion.id)))
    assert count == first["discovered"]
    assert version_count == first["discovered"]

    sap = await service.get_profile("ks_lbp_disposition_v2")
    sap_data = await service.profile_data(sap)
    assert sap_data["protected"] is True
    assert sap_data["lifecycle"] == "active"
    assert sap_data["adapter_status"] == "available"

    business_central = await service.get_profile("business_central_customer_master_v1")
    bc_data = await service.profile_data(business_central)
    assert bc_data["protected"] is True
    assert bc_data["lifecycle"] == "candidate"
    assert bc_data["active_version_id"] is None
    assert bc_data["adapter_id"] == "canonical_entity_map_v1"
    assert bc_data["adapter_status"] == "available"
    assert bc_data["required_adapter_status"] == "available"
    assert bc_data["versions"][0]["validation_report"]["static"]["enterprise_schema_valid"] is True


@pytest.mark.asyncio
async def test_bundled_sync_repairs_protected_profile_and_active_pointer(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    await service.sync_bundled_profiles()
    sap = await service.get_profile("ks_lbp_disposition_v2")
    sap.protected = False
    sap.is_deleted = True
    sap.active_version_id = None
    sap.lifecycle_status = "retired"
    await registry_session.flush()

    stats = await service.sync_bundled_profiles()
    repaired = await service.get_profile("ks_lbp_disposition_v2")

    assert stats["profiles_repaired"] >= 1
    assert repaired.protected is True
    assert repaired.is_deleted is False
    assert repaired.lifecycle_status == "active"
    assert repaired.active_version_id is not None


@pytest.mark.asyncio
async def test_candidate_validation_executes_fixtures_then_promotes_and_resolves_trust(
    registry_session,
):
    service = TransformationProfileRegistryService(registry_session)
    candidate = await service.create_candidate(_candidate_body())

    with pytest.raises(TransformationProfileLifecycleError, match="has no active version"):
        await service.resolve_active_definition("test_customer_v1")
    with pytest.raises(TransformationProfileLifecycleError, match="positive validation fixture"):
        await service.validate_candidate(
            candidate.id,
            TransformationProfileValidationRequest(actor="skillopt"),
        )

    validated = await service.validate_candidate(candidate.id, _validation_evidence())
    assert validated.status == "validated"
    assert validated.validation_score == 1.0
    assert validated.validation_report["gates"] == {
        "schema_valid": True,
        "fixtures_passed": True,
        "negative_fixtures_passed": True,
        "security_passed": True,
        "reconciliation_passed": True,
    }

    active = await service.promote(candidate.id, actor="skillopt")
    assert active.status == "active"
    snapshot = await service.resolve_active_definition(
        "test_customer_v1",
        expected_version=1,
        expected_hash=active.content_hash,
    )
    assert snapshot["definition"] == active.definition
    assert snapshot["registry_evidence"] == {
        "profile_id": "test_customer_v1",
        "version": 1,
        "content_hash": active.content_hash,
        "status": "active",
        "adapter_id": "canonical_entity_map_v1",
        "adapter_status": "available",
        "version_id": str(active.id),
    }
    # Trust stamping is isolated; the immutable candidate content is untouched.
    assert snapshot["definition"]["lifecycle"] == "candidate"
    assert active.definition["lifecycle"] == "candidate"
    with pytest.raises(TransformationProfileLifecycleError, match="not pinned version 2"):
        await service.resolve_active_definition("test_customer_v1", expected_version=2)
    with pytest.raises(TransformationProfileLifecycleError, match="does not match the AgentFlow pin"):
        await service.resolve_active_definition("test_customer_v1", expected_hash="0" * 64)


@pytest.mark.asyncio
async def test_negative_fixture_must_really_fail(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    candidate = await service.create_candidate(_candidate_body("negative_guard_v1"))

    with pytest.raises(TransformationProfileLifecycleError, match="incorrectly accepted"):
        await service.validate_candidate(
            candidate.id,
            _validation_evidence(negative_payload={"id": "this-is-valid"}),
        )
    assert candidate.status == "candidate"


@pytest.mark.asyncio
async def test_unregistered_adapter_cannot_validate_or_promote(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    candidate = await service.create_candidate(
        _candidate_body("future_adapter_v1", adapter="future_api_adapter_v1")
    )
    adapter = await registry_session.get(TransformationAdapter, "future_api_adapter_v1")
    assert adapter.status == "unavailable"

    with pytest.raises(TransformationAdapterUnavailableError, match="fail-closed"):
        await service.validate_candidate(candidate.id, _validation_evidence())


@pytest.mark.asyncio
async def test_promotion_requires_server_generated_validation_report(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    candidate = await service.create_candidate(_candidate_body("forged_validation_v1"))
    candidate.status = "validated"
    candidate.validation_score = 1.0
    candidate.validation_report = {"caller_claimed": True}
    await registry_session.flush()

    with pytest.raises(TransformationProfileLifecycleError, match="server-executed"):
        await service.promote(candidate.id, actor="attacker")


@pytest.mark.asyncio
async def test_promotion_retires_previous_and_rollback_creates_auditable_version(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    first = await service.create_candidate(_candidate_body("rollback_customer_v1"))
    await service.validate_candidate(first.id, _validation_evidence())
    await service.promote(first.id, actor="skillopt")

    updated_definition = json.loads(json.dumps(first.definition))
    updated_definition["description"] = "Second mapping revision"
    second_body = _candidate_body("rollback_customer_v1")
    second_body.definition = updated_definition
    second = await service.create_candidate(second_body)
    await service.validate_candidate(second.id, _validation_evidence())
    await service.promote(second.id, actor="skillopt")
    assert first.status == "retired"
    assert second.status == "active"

    rollback = await service.rollback(
        "rollback_customer_v1", target_version=1, actor="operator"
    )
    assert rollback.version_number == 3
    assert rollback.origin == "rollback"
    assert rollback.status == "active"
    assert rollback.definition == first.definition
    assert rollback.content_hash == profile_content_hash(first.definition)
    assert second.status == "retired"


@pytest.mark.asyncio
async def test_bundle_repair_never_overwrites_skillopt_active_version(
    registry_session,
    tmp_path,
):
    profile_id = "bundle_upgrade_guard_v1"
    bundled_definition = _canonical_manifest(profile_id)
    (tmp_path / f"{profile_id}.json").write_text(
        json.dumps(bundled_definition),
        encoding="utf-8",
    )
    service = TransformationProfileRegistryService(registry_session)
    await service.sync_bundled_profiles(tmp_path)

    learned_definition = json.loads(json.dumps(bundled_definition))
    learned_definition["description"] = "SkillOpt learned revision"
    learned = await service.create_candidate(
        TransformationProfileCandidateCreate(
            profile_id=profile_id,
            display_name="Bundle upgrade guard",
            platform="Test ERP",
            domain="erp",
            adapter_id="canonical_entity_map_v1",
            definition=learned_definition,
            origin="skillopt",
            actor="skillopt",
        )
    )
    await service.validate_candidate(learned.id, _validation_evidence())
    await service.promote(learned.id, actor="skillopt")

    await service.sync_bundled_profiles(tmp_path)
    profile = await service.get_profile(profile_id)
    active = await service.resolve_active_definition(profile_id)

    assert profile.active_version_id == learned.id
    assert active["registry_evidence"]["version"] == 2
    assert active["definition"]["description"] == "SkillOpt learned revision"


@pytest.mark.asyncio
async def test_protected_bundled_profile_cannot_be_deleted(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    await service.sync_bundled_profiles()

    with pytest.raises(ProtectedTransformationProfileError, match="cannot be deleted"):
        await service.delete_profile("ks_lbp_disposition_v2", actor="operator")
