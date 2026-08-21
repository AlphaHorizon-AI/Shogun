"""Portable private profiles remain flow-local and execute fail-closed."""

from __future__ import annotations

import time
from copy import deepcopy

import pytest
from pydantic import ValidationError

from shogun.config import settings
from shogun.engine import flow_engine
from shogun.mapping.errors import MappingSchemaError
from shogun.mapping.schema import MappingConfig
from shogun.services.private_transformation_profiles import (
    PrivateTransformationProfileError,
    PrivateTransformationProfileRegexError,
    PrivateTransformationProfileService,
)
from shogun.services.transformation_profile_registry import profile_content_hash


def _sectioned_profile() -> dict:
    return {
        "id": "private_supplier_schedule_v1",
        "adapter": "sectioned_record_matrix_v1",
        "parameters": {
            "required_source_patterns": [r"(?m)^Record:\s*\S+"],
            "section_pattern": r"(?m)^Record:\s*(?P<section_id>\S+)",
            "section_key_group": "section_id",
            "record_pattern": r"(?m)^Item:\s*(?P<kind>\S+)\s+(?P<value>\S+)$",
            "record_section_key_group": "",
            "row_rules": [
                {
                    "kind": "record",
                    "columns": {"0": {"group": "value"}},
                }
            ],
        },
        "model_fallback": False,
    }


def _canonical_profile() -> dict:
    return {
        "resource_type": "transformation_profile",
        "manifest_version": "1.0",
        "id": "private_customer_v1",
        "version": 1,
        "lifecycle": "candidate",
        "profile_kind": "canonical_ingress",
        "adapter": "canonical_entity_map_v1",
        "parameters": {},
        "platform": {"vendor": "Private", "product": "ERP", "family": "erp"},
        "source": {"transport": "rest", "object": "customers", "record_shape": "entity"},
        "canonical_contract": {
            "id": "customer_master",
            "version": 1,
            "record_kind": "customer",
        },
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
            "classification": "confidential",
            "pii_fields": [],
            "secret_fields": [],
            "retention": "flow_policy",
        },
        "adapter_requirements": {
            "adapter": "canonical_entity_map_v1",
            "minimum_version": 1,
            "status": "available",
            "capabilities": ["field_mapping"],
            "fail_closed": True,
        },
        "selection": {"positive_fingerprints": [], "negative_fingerprints": []},
        "model_fallback": False,
    }


def test_private_profile_export_import_is_hash_pinned_and_flow_local():
    service = PrivateTransformationProfileService()
    exported = service.export_profile(
        _sectioned_profile(),
        execution_mode="contract",
        display_name="Supplier confidential schedule",
    )

    assert set(exported) == {"filename", "execution_mode", "document", "profile_reference"}
    assert exported["execution_mode"] == "contract"
    assert exported["filename"] == "Supplier-confidential-schedule.shogun-profile.json"
    assert exported["document"]["format"] == "shogun.private-transformation-profile"
    assert exported["document"]["content_hash"] == exported["profile_reference"][
        "private_file"
    ]["content_hash"]
    reference = exported["profile_reference"]
    assert "registry_version" not in reference
    assert "content_hash" not in reference
    assert reference["private_file"]["definition"] == _sectioned_profile()

    imported = service.import_document(exported["document"])
    assert imported["execution_mode"] == "contract"
    assert imported["profile_reference"] == reference
    config = MappingConfig.model_validate(
        {
            "execution_mode": "contract",
            "transformation_profile": reference,
        }
    )
    assert config.transformation_profile is not None
    assert config.transformation_profile.is_private_file is True
    assert config.transformation_profile.is_registry_pinned is False


def test_private_profile_file_rejects_tampering_credentials_and_unsupported_adapters():
    service = PrivateTransformationProfileService()
    exported = service.export_profile(_sectioned_profile())
    tampered = deepcopy(exported["document"])
    tampered["profile"]["parameters"]["section_pattern"] = "caller changed mechanics"
    with pytest.raises((PrivateTransformationProfileError, ValidationError), match="content_hash"):
        service.import_document(tampered)

    credentialed = _sectioned_profile()
    credentialed["parameters"]["credentials"] = {"password": "do-not-store"}
    with pytest.raises(PrivateTransformationProfileError, match="cannot contain credentials"):
        service.export_profile(credentialed)

    unsupported = _sectioned_profile()
    unsupported["adapter"] = "arbitrary_python_v1"
    with pytest.raises(PrivateTransformationProfileError, match="not supported"):
        service.export_profile(unsupported)


def test_private_profile_file_enforces_two_megabyte_limit_and_mode_compatibility():
    service = PrivateTransformationProfileService()
    oversized = _sectioned_profile()
    oversized["parameters"]["padding"] = "x" * 2_000_000
    with pytest.raises(
        (PrivateTransformationProfileError, ValidationError),
        match=r"(?:2 MB|2000000-byte)",
    ):
        service.export_profile(oversized)
    with pytest.raises(PrivateTransformationProfileError, match="executes in 'contract'"):
        service.export_profile(_sectioned_profile(), execution_mode="profile")


def test_private_profile_import_rejects_pathological_source_regex_quickly():
    service = PrivateTransformationProfileService()
    pathological = _sectioned_profile()
    pathological["parameters"]["required_source_patterns"] = [r"(a+)+$"]
    document = {
        "format": "shogun.private-transformation-profile",
        "format_version": 1,
        "content_hash": profile_content_hash(pathological),
        "profile": pathological,
    }

    started = time.monotonic()
    with pytest.raises(
        PrivateTransformationProfileRegexError,
        match="nested variable quantifiers",
    ):
        service.import_document(document)

    assert time.monotonic() - started < 0.5


def test_private_profile_import_rejects_deeply_nested_source_regex():
    service = PrivateTransformationProfileService()
    deeply_nested = _sectioned_profile()
    deeply_nested["parameters"]["required_source_patterns"] = [
        ("(" * 600) + "a" + (")" * 600)
    ]
    document = {
        "format": "shogun.private-transformation-profile",
        "format_version": 1,
        "content_hash": profile_content_hash(deeply_nested),
        "profile": deeply_nested,
    }

    with pytest.raises(
        PrivateTransformationProfileRegexError,
        match="Invalid regex|could not pass safety analysis",
    ):
        service.import_document(document)


def test_private_canonical_profile_enforces_source_pattern_limit():
    service = PrivateTransformationProfileService()
    oversized = _canonical_profile()
    oversized["parameters"]["required_source_patterns"] = [
        rf"marker-{index}" for index in range(33)
    ]

    with pytest.raises(
        PrivateTransformationProfileRegexError,
        match="32 source-fingerprint regex limit",
    ):
        service.export_profile(oversized)


@pytest.mark.anyio
async def test_registry_pin_is_resolved_before_private_export():
    definition = _sectioned_profile()
    direct = PrivateTransformationProfileService().export_profile(definition)
    digest = direct["document"]["content_hash"]

    class Registry:
        async def resolve_active_definition(
            self,
            profile_id,
            *,
            expected_version,
            expected_hash,
        ):
            assert profile_id == definition["id"]
            assert expected_version == 3
            assert expected_hash == digest
            return {
                "definition": definition,
                "registry_evidence": {
                    "profile_id": definition["id"],
                    "adapter_id": definition["adapter"],
                },
            }

    exported = await PrivateTransformationProfileService().export_profile_reference(
        {
            "id": definition["id"],
            "adapter": definition["adapter"],
            "parameters": {},
            "registry_version": 3,
            "content_hash": digest,
        },
        registry_service=Registry(),
        execution_mode="contract",
    )
    assert exported["document"]["profile"] == definition
    assert exported["profile_reference"]["private_file"]["content_hash"] == digest


@pytest.mark.anyio
async def test_private_contract_executes_without_a_registry_record_and_carrier_is_rechecked():
    service = PrivateTransformationProfileService()
    reference = service.export_profile(_sectioned_profile())["profile_reference"]
    result = await flow_engine._exec_mapping_rpa(
        {
            "execution_mode": "contract",
            "transformation_profile": reference,
        },
        {},
        flow_id="flow-private",
        node_id="private-contract",
    )

    assert result["status"] == "SUCCESS"
    assert result["registry_evidence"]["status"] == "private_validated"
    assert result["registry_evidence"]["source"] == "private_file"
    assert result["registry_evidence"]["server_validated"] is True
    profile = MappingConfig.model_validate(
        {
            "execution_mode": "contract",
            "transformation_profile": reference,
        }
    ).transformation_profile
    assert profile is not None
    assert flow_engine._trusted_contract_profile_from_carrier(
        profile,
        result,
        carrier_label="Private supplier contract",
    ) == _sectioned_profile()

    forged = deepcopy(result)
    forged["resolved_definition"]["parameters"]["section_pattern"] = "forged"
    with pytest.raises(MappingSchemaError, match="content-hash pin"):
        flow_engine._trusted_contract_profile_from_carrier(
            profile,
            forged,
            carrier_label="Private supplier contract",
        )


@pytest.mark.anyio
async def test_private_canonical_profile_executes_with_server_validated_evidence():
    reference = PrivateTransformationProfileService().export_profile(
        _canonical_profile(),
        execution_mode="profile",
    )["profile_reference"]
    result = await flow_engine._exec_mapping_rpa(
        {
            "execution_mode": "profile",
            "transformation_profile": reference,
            "output": {"type": "table", "start_cell": "A1"},
        },
        {"source": {"id": " C-1 "}},
        flow_id="flow-private",
        node_id="private-canonical",
    )

    assert result["status"] == "SUCCESS"
    assert result["canonical"]["records"] == [{"customer_id": "C-1"}]
    assert result["profile"]["id"] == "private_customer_v1"


@pytest.mark.anyio
async def test_private_profile_import_export_api_returns_assignable_reference(client):
    headers = {
        "X-Shogun-Infrastructure-Token": str(settings.infrastructure_admin_token or "")
    }
    exported = await client.post(
        "/api/v1/transformation-profiles/private-files/export",
        headers=headers,
        json={"profile": _sectioned_profile(), "execution_mode": "contract"},
    )
    assert exported.status_code == 200
    exported_data = exported.json()["data"]
    assert set(exported_data) == {
        "filename",
        "execution_mode",
        "document",
        "profile_reference",
    }
    assert exported_data["execution_mode"] == "contract"

    imported = await client.post(
        "/api/v1/transformation-profiles/private-files/import",
        headers=headers,
        json={"document": exported_data["document"]},
    )
    assert imported.status_code == 200
    imported_data = imported.json()["data"]
    assert set(imported_data) == {
        "filename",
        "execution_mode",
        "document",
        "profile_reference",
    }
    assert imported_data["execution_mode"] == "contract"
    MappingConfig.model_validate(
        {
            "execution_mode": "contract",
            "transformation_profile": imported_data["profile_reference"],
        }
    )


@pytest.mark.anyio
async def test_mapping_preview_executes_private_canonical_profile(client):
    headers = {
        "X-Shogun-Infrastructure-Token": str(settings.infrastructure_admin_token or "")
    }
    reference = PrivateTransformationProfileService().export_profile(
        _canonical_profile(),
        execution_mode="profile",
    )["profile_reference"]

    response = await client.post(
        "/api/v1/mapping-rpa/preview",
        headers=headers,
        json={
            "config": {
                "execution_mode": "profile",
                "transformation_profile": reference,
                "output": {"type": "table", "start_cell": "A1"},
            },
            "input": {"id": " C-1 "},
        },
    )

    assert response.status_code == 200
    result = response.json()["data"]
    assert result["status"] == "SUCCESS"
    assert result["canonical"]["records"] == [{"customer_id": "C-1"}]
    assert result["profile"]["id"] == "private_customer_v1"
    assert result["type"] == "table"
    assert result["start_cell"] == "A1"
