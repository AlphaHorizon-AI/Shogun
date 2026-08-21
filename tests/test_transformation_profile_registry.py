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
        "selection": {"positive_fingerprints": ["field:id"], "negative_fingerprints": []},
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
                    # Preserve the declared field fingerprint while proving
                    # that blank canonical identity is rejected separately.
                    "payload": {"id": " "} if negative_payload is None else negative_payload,
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
    assert all(item.lifecycle == "candidate" for item in descriptors)


@pytest.mark.asyncio
async def test_bundled_sync_validates_activates_and_reuses_package_evidence(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    first = await service.sync_bundled_profiles()
    await registry_session.commit()
    second = await service.sync_bundled_profiles()

    assert first["discovered"] >= 80
    assert first["profiles_created"] == first["discovered"]
    assert first["validated"] == first["discovered"] == 86
    assert first["activated"] == 86
    assert first["active_profiles"] == 86
    assert first["candidate_profiles"] == 0
    assert first["bundled_active_profiles"] == 86
    assert first["bundled_candidate_profiles"] == 0
    assert second["profiles_created"] == 0
    assert second["versions_created"] == 0
    assert second["validation_reused"] == 86
    assert second["activated"] == 0
    count = await registry_session.scalar(select(func.count(RegisteredTransformationProfile.id)))
    version_count = await registry_session.scalar(select(func.count(TransformationProfileVersion.id)))
    assert count == first["discovered"]
    assert version_count == first["discovered"]

    catalog = await service.list_profiles()
    assert len(catalog) == 86
    assert all(item["lifecycle"] == "active" for item in catalog)
    assert all(item["selectable"] is True for item in catalog)
    assert all(item["blockers"] == [] for item in catalog)
    for item in catalog:
        detail = await service.profile_data(
            await service.get_profile(item["profile_id"])
        )
        report = detail["versions"][0]["validation_report"]
        assert report["package_validation"]["passed"] is True
        assert len(report["fixtures"]["positive_fixtures"]) == 3
        assert len(report["fixtures"]["negative_fixtures"]) >= 2

    business_central = await service.get_profile("business_central_customer_master_v1")
    business_central_version = await registry_session.get(
        TransformationProfileVersion,
        business_central.active_version_id,
    )
    assert business_central_version is not None
    business_central_version.validation_report = {
        **business_central_version.validation_report,
        "fixtures": {},
    }
    await registry_session.flush()
    repaired_evidence = await service.sync_bundled_profiles()
    assert repaired_evidence["validated"] == 1
    assert repaired_evidence["validation_reused"] == 85

    bc_data = await service.profile_data(business_central)
    assert bc_data["protected"] is True
    assert bc_data["lifecycle"] == "active"
    assert bc_data["active_version_id"] is not None
    assert bc_data["adapter_id"] == "canonical_entity_map_v1"
    assert bc_data["adapter_status"] == "available"
    assert bc_data["required_adapter_status"] == "available"
    assert bc_data["selectable"] is True
    assert bc_data["execution_mode"] == "profile"
    assert bc_data["blockers"] == []
    assert bc_data["source_requirement"]["transport"] == "rest"
    assert bc_data["versions"][0]["validation_report"]["static"]["enterprise_schema_valid"] is True
    assert bc_data["versions"][0]["validation_report"]["package_validation"]["passed"] is True
    assert len(bc_data["versions"][0]["validation_report"]["fixtures"]["positive_fixtures"]) == 3
    assert len(bc_data["versions"][0]["validation_report"]["fixtures"]["negative_fixtures"]) >= 2


@pytest.mark.asyncio
async def test_bundled_sync_repairs_and_reactivates_protected_profile(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    await service.sync_bundled_profiles()
    profile_id = "business_central_customer_master_v1"
    profile = await service.get_profile(profile_id)
    profile.protected = False
    profile.is_deleted = True
    profile.active_version_id = None
    profile.lifecycle_status = "retired"
    await registry_session.flush()

    stats = await service.sync_bundled_profiles()
    repaired = await service.get_profile(profile_id)

    assert stats["profiles_repaired"] >= 1
    assert repaired.protected is True
    assert repaired.is_deleted is False
    assert repaired.lifecycle_status == "active"
    assert repaired.active_version_id is not None


@pytest.mark.asyncio
async def test_generic_sectioned_matrix_bundle_is_candidate_not_package_trusted(
    registry_session,
    tmp_path,
):
    profile_id = "synthetic_sectioned_report_v1"
    definition = _canonical_manifest(
        profile_id,
        adapter="sectioned_record_matrix_v1",
    )
    definition["title"] = "Synthetic sectioned report"
    definition["parameters"] = {
        "section_pattern": r"(?m)^Entity: (?P<section_id>\S+)$",
        "record_pattern": r"(?m)^Line: (?P<entity>\S+) (?P<value>\d+)$",
        "record_section_key_group": "entity",
        "row_rules": [{"kind": "record"}],
    }
    (tmp_path / f"{profile_id}.json").write_text(
        json.dumps(definition),
        encoding="utf-8",
    )

    service = TransformationProfileRegistryService(registry_session)
    stats = await service.sync_bundled_profiles(tmp_path)
    profile = await service.get_profile(profile_id)
    data = await service.profile_data(profile)

    assert stats["discovered"] == 1
    assert stats["activated"] == 0
    assert data["lifecycle"] == "candidate"
    assert data["active_version_id"] is None
    assert data["adapter_id"] == "sectioned_record_matrix_v1"
    assert data["adapter_status"] == "available"
    assert data["selectable"] is False
    assert data["execution_mode"] == "contract"
    assert data["blockers"] == [
        "Profile has not passed executable fixture validation and promotion."
    ]


@pytest.mark.asyncio
async def test_removed_bundle_is_localized_without_deleting_active_customer_data(
    registry_session,
    tmp_path,
):
    old_root = tmp_path / "old_bundle"
    new_root = tmp_path / "new_bundle"
    old_root.mkdir()
    new_root.mkdir()
    profile_id = "former_customer_bundle_v1"
    definition = _canonical_manifest(
        profile_id,
        adapter="sectioned_record_matrix_v1",
    )
    (old_root / f"{profile_id}.json").write_text(
        json.dumps(definition),
        encoding="utf-8",
    )

    service = TransformationProfileRegistryService(registry_session)
    await service.sync_bundled_profiles(old_root)
    profile = await service.get_profile(profile_id)
    version = await registry_session.scalar(
        select(TransformationProfileVersion).where(
            TransformationProfileVersion.profile_id == profile.id
        )
    )
    assert version is not None
    version.status = "active"
    profile.lifecycle_status = "active"
    profile.active_version_id = version.id
    await registry_session.flush()

    stats = await service.sync_bundled_profiles(new_root)
    preserved = await service.get_profile(profile_id)
    preserved_version = await service.resolve_active_definition(profile_id)

    assert stats["profiles_localized"] == 1
    assert preserved.bundled is False
    assert preserved.protected is False
    assert preserved.source_resource is None
    assert preserved.lifecycle_status == "active"
    assert preserved.active_version_id == version.id
    assert preserved.metadata_json["distribution"] == "local_private"
    assert "bundled_manifest_hash" not in preserved.metadata_json
    assert preserved_version["definition"] == definition


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
async def test_promotion_rejects_profile_with_planned_adapter_requirements(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    definition = _canonical_manifest("planned_capability_v1")
    definition["adapter_requirements"]["status"] = "planned"
    candidate = await service.create_candidate(
        TransformationProfileCandidateCreate(
            profile_id="planned_capability_v1",
            display_name="Planned capability",
            platform="Test ERP",
            domain="erp",
            adapter_id="canonical_entity_map_v1",
            definition=definition,
        )
    )
    candidate.status = "validated"
    candidate.validation_score = 1.0
    candidate.validation_report = {
        "gates": {
            "schema_valid": True,
            "fixtures_passed": True,
            "negative_fixtures_passed": True,
            "security_passed": True,
            "reconciliation_passed": True,
        }
    }
    await registry_session.flush()

    with pytest.raises(
        TransformationAdapterUnavailableError,
        match="requires adapter status 'planned'",
    ):
        await service.promote(candidate.id, actor="skillopt")


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
    monkeypatch,
):
    profile_id = "bundle_upgrade_guard_v1"
    bundled_definition = _canonical_manifest(profile_id)
    (tmp_path / f"{profile_id}.json").write_text(
        json.dumps(bundled_definition),
        encoding="utf-8",
    )
    bundled_descriptor = discover_bundled_profile_manifests(tmp_path)[0]
    monkeypatch.setattr(
        "shogun.services.transformation_profile_registry.discover_bundled_profile_manifests",
        lambda resource_root=None: [bundled_descriptor],
    )
    service = TransformationProfileRegistryService(registry_session)
    first_sync = await service.sync_bundled_profiles()
    assert first_sync["activated"] == 1

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

    # Older installations can contain a retired bundle stamped active by a
    # former package policy but without server-executed gates. Repairing that
    # legacy seed must not make the promoted tenant version look unselectable.
    bundled_version = await registry_session.scalar(
        select(TransformationProfileVersion).where(
            TransformationProfileVersion.profile_id == learned.profile_id,
            TransformationProfileVersion.origin == "bundled",
        )
    )
    assert bundled_version is not None
    bundled_version.status = "retired"
    bundled_version.validation_report = {"bundled": True}
    await registry_session.flush()
    legacy_stats = await service.sync_bundled_profiles()
    repaired_profile = await service.get_profile(profile_id)
    assert legacy_stats["tenant_active_preserved"] == 1
    assert repaired_profile.lifecycle_status == "active"
    assert repaired_profile.active_version_id == learned.id

    refreshed_definition = json.loads(json.dumps(bundled_definition))
    refreshed_definition["description"] = "New package revision"
    (tmp_path / f"{profile_id}.json").write_text(
        json.dumps(refreshed_definition),
        encoding="utf-8",
    )
    refreshed_descriptor = discover_bundled_profile_manifests(tmp_path)[0]
    monkeypatch.setattr(
        "shogun.services.transformation_profile_registry.discover_bundled_profile_manifests",
        lambda resource_root=None: [refreshed_descriptor],
    )
    refresh_stats = await service.sync_bundled_profiles()
    profile = await service.get_profile(profile_id)
    active = await service.resolve_active_definition(profile_id)

    assert refresh_stats["validated"] == 1
    assert refresh_stats["tenant_active_preserved"] == 1
    assert refresh_stats["activated"] == 0
    assert profile.active_version_id == learned.id
    assert active["registry_evidence"]["version"] == 2
    assert active["definition"]["description"] == "SkillOpt learned revision"


@pytest.mark.asyncio
async def test_bundle_refresh_promotes_new_validated_bundle_over_old_bundle(
    registry_session,
    tmp_path,
    monkeypatch,
):
    profile_id = "bundle_package_upgrade_v1"
    original = _canonical_manifest(profile_id)
    resource = tmp_path / f"{profile_id}.json"
    resource.write_text(json.dumps(original), encoding="utf-8")
    first_descriptor = discover_bundled_profile_manifests(tmp_path)[0]
    monkeypatch.setattr(
        "shogun.services.transformation_profile_registry.discover_bundled_profile_manifests",
        lambda resource_root=None: [first_descriptor],
    )
    service = TransformationProfileRegistryService(registry_session)
    await service.sync_bundled_profiles()
    profile = await service.get_profile(profile_id)
    first_active_id = profile.active_version_id

    refreshed = json.loads(json.dumps(original))
    refreshed["description"] = "Validated package upgrade"
    resource.write_text(json.dumps(refreshed), encoding="utf-8")
    refreshed_descriptor = discover_bundled_profile_manifests(tmp_path)[0]
    monkeypatch.setattr(
        "shogun.services.transformation_profile_registry.discover_bundled_profile_manifests",
        lambda resource_root=None: [refreshed_descriptor],
    )
    stats = await service.sync_bundled_profiles()
    active = await service.resolve_active_definition(profile_id)

    assert stats["validated"] == 1
    assert stats["activated"] == 1
    assert profile.active_version_id != first_active_id
    assert active["registry_evidence"]["version"] == 2
    assert active["definition"]["description"] == "Validated package upgrade"


@pytest.mark.asyncio
async def test_protected_bundled_profile_cannot_be_deleted(registry_session):
    service = TransformationProfileRegistryService(registry_session)
    await service.sync_bundled_profiles()

    with pytest.raises(ProtectedTransformationProfileError, match="cannot be deleted"):
        await service.delete_profile("business_central_customer_master_v1", actor="operator")
