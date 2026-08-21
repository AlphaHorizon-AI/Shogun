from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from shogun.mapping.errors import MappingError
from shogun.services.bundled_transformation_profile_fixtures import (
    BUNDLED_FIXTURE_POLICY,
    build_bundled_validation_request,
)
from shogun.services.enterprise_transformations import (
    enterprise_profile_content_hash,
    execute_enterprise_profile,
)

PROFILE_DIR = (
    Path(__file__).resolve().parents[1]
    / "shogun"
    / "resources"
    / "transformation_profiles"
)
CATALOG_PATH = PROFILE_DIR / "catalog_v1.json"
ENTERPRISE_ADAPTER = "canonical_entity_map_v1"

EXPECTED_PLATFORM_COUNTS = {
    "Business Central": 9,
    "D365 Finance & Supply Chain": 10,
    "e-conomic": 5,
    "Epicor Kinetic": 5,
    "HubSpot": 5,
    "IFS Cloud": 5,
    "NetSuite": 9,
    "Oracle Fusion ERP/SCM": 5,
    "QuickBooks Online": 5,
    "Sage Intacct": 5,
    "Salesforce": 7,
    "ServiceNow": 5,
    "Workday": 6,
    "Xero": 5,
}
RUNTIME_FIELD_TYPES = {
    "any",
    "array",
    "boolean",
    "currency",
    "date",
    "datetime",
    "decimal",
    "id",
    "integer",
    "number",
    "object",
    "string",
}
RUNTIME_TRANSFORMS = {
    "date_normalize",
    "datetime_normalize",
    "decimal_normalize",
    "lowercase",
    "number_normalize",
    "replace",
    "strip_leading_zero",
    "trim",
    "uppercase",
}
RUNTIME_INVARIANTS = {
    "debits_equal_credits",
    "equals",
    "greater_than",
    "header_equals_line_sum_with_tolerance",
    "mutually_exclusive_nonzero",
    "nonnegative",
    "required_fields_present",
    "required_non_blank",
    "required_nonempty",
    "sum_equals",
    "unique_composite",
}
V2_ONLY_CAPABILITIES = {
    "heterogeneous_object_union",
    "nested_collection_flattening",
    "synthetic_line_index",
    "business_rule:debits_equal_credits",
    "business_rule:greater_than",
    "business_rule:header_equals_line_sum_with_tolerance",
    "business_rule:mutually_exclusive_nonzero",
    "business_rule:required_fields_present",
    "business_rule:sum_equals",
    "business_rule:unique_composite",
}
FORBIDDEN_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "base_url",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "tenant_url",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict), path.name
    return value


def _catalog() -> dict[str, Any]:
    return _load(CATALOG_PATH)


def _enterprise_profiles() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for entry in _catalog()["profiles"]:
        result[entry["id"]] = _load(PROFILE_DIR / entry["resource"])
    return result


def _walk_keys(value: Any):
    if isinstance(value, dict):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _walk_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_strings(child)


def test_catalog_indexes_every_bundled_profile_resource_once():
    catalog = _catalog()
    assert catalog["resource_type"] == "transformation_profile_catalog"
    assert catalog["catalog_version"] == 1

    entries = catalog["profiles"]
    ids = [entry["id"] for entry in entries]
    resources = [entry["resource"] for entry in entries]
    disk_resources = {
        path.name
        for path in PROFILE_DIR.glob("*.json")
        if path.name != CATALOG_PATH.name
    }

    assert len(entries) == 86
    assert len(ids) == len(set(ids))
    assert len(resources) == len(set(resources))
    assert set(resources) == disk_resources
    assert catalog["totals"] == {
        "profiles": 86,
        "active": 86,
        "candidates": 0,
        "adapter_available": 86,
        "adapter_planned": 0,
    }
    assert all(entry["lifecycle"] == "active" for entry in entries)
    assert all(entry["adapter_status"] == "available" for entry in entries)
    assert catalog["platform_counts"] == EXPECTED_PLATFORM_COUNTS
    assert Counter(entry["platform"] for entry in entries) == EXPECTED_PLATFORM_COUNTS


def test_enterprise_profile_manifests_are_complete_and_identity_safe():
    profiles = _enterprise_profiles()
    assert len(profiles) == 86

    for profile_id, profile in profiles.items():
        assert profile["resource_type"] == "transformation_profile", profile_id
        assert profile["manifest_version"] == "1.0", profile_id
        assert profile["id"] == profile_id
        assert profile["version"] == 1
        assert profile["lifecycle"] == "candidate"
        assert profile["profile_kind"] == "canonical_ingress"
        assert profile["adapter"] == ENTERPRISE_ADAPTER
        assert profile["parameters"] == {}
        assert all(profile["platform"].get(key) for key in ("vendor", "product", "family"))
        assert all(
            profile["source"].get(key)
            for key in ("transport", "api_version", "object", "record_shape", "pagination")
        )
        assert all(
            profile["canonical_contract"].get(key)
            for key in ("id", "version", "record_kind")
        )

        mappings = profile["field_map"]
        assert len(mappings) >= 6, profile_id
        sources = [mapping["source"] for mapping in mappings]
        targets = [mapping["target"] for mapping in mappings]
        assert len(targets) == len(set(targets)), profile_id
        assert set(profile["identity"]["source_key"]) <= set(sources), profile_id
        assert set(profile["identity"]["canonical_key"]) <= set(targets), profile_id
        assert profile["identity"]["conflict_policy"] == "error"

        required_targets = {
            mapping["target"] for mapping in mappings if mapping["required"]
        }
        assert set(profile["identity"]["canonical_key"]) <= required_targets
        assert set(profile["privacy"]["pii_fields"]) <= set(targets)
        assert profile["privacy"]["secret_fields"] == []
        assert profile["privacy"]["retention"] == "inherit_flow_policy"

        requirements = profile["adapter_requirements"]
        assert requirements["adapter"] == ENTERPRISE_ADAPTER
        assert requirements["minimum_version"] in {1, 2}
        assert requirements["status"] == "available"
        assert requirements["fail_closed"] is True
        assert requirements["capabilities"]
        if set(requirements["capabilities"]) & V2_ONLY_CAPABILITIES:
            assert requirements["minimum_version"] >= 2, profile_id

        selection = profile["selection"]
        assert selection["positive_fingerprints"]
        assert any(
            str(value).startswith("field:")
            for value in selection["positive_fingerprints"]
        )
        for fingerprint in (
            selection["positive_fingerprints"]
            + selection["negative_fingerprints"]
        ):
            assert re.match(r"^(field|path|object|transport):", fingerprint), (
                profile_id,
                fingerprint,
            )


def test_available_profiles_use_only_the_executable_adapter_vocabulary():
    for profile_id, profile in _enterprise_profiles().items():
        if profile["adapter_requirements"]["status"] != "available":
            continue

        for mapping in profile["field_map"]:
            assert mapping["type"] in RUNTIME_FIELD_TYPES, (profile_id, mapping)
            for transform in mapping.get("transforms", []):
                name = transform if isinstance(transform, str) else transform.get("name")
                assert name in RUNTIME_TRANSFORMS, (profile_id, transform)

        assert all(
            invariant["rule"] in RUNTIME_INVARIANTS
            for invariant in profile["invariants"]
        ), profile_id
        identity_invariant = profile["invariants"][0]
        assert identity_invariant["id"] == "identity_complete"
        assert identity_invariant["rule"] in {"required_nonempty", "required_non_blank"}
        assert identity_invariant["fields"] == profile["identity"]["canonical_key"]

        mappings_by_target = {mapping["target"]: mapping for mapping in profile["field_map"]}
        for invariant in profile["invariants"]:
            if invariant["rule"] != "header_equals_line_sum_with_tolerance":
                continue
            header_total = invariant["fields"][0]
            assert mappings_by_target[header_total]["required"] is True, profile_id
            assert isinstance(invariant.get("tolerance"), (int, float)), profile_id
            assert invariant["tolerance"] >= 0, profile_id


def test_profile_resources_contain_no_credentials_or_tenant_urls():
    for profile_id, profile in _enterprise_profiles().items():
        normalized_keys = {
            re.sub(r"[^a-z0-9]+", "_", key.casefold()).strip("_")
            for key in _walk_keys(profile)
        }
        assert not (normalized_keys & FORBIDDEN_KEYS), profile_id
        assert all("://" not in value for value in _walk_strings(profile)), profile_id


def test_all_catalog_profiles_pass_package_owned_executable_fixture_gates():
    profiles = _enterprise_profiles()
    assert len(profiles) == 86

    for profile_id, profile in profiles.items():
        evidence = build_bundled_validation_request(profile)
        assert evidence.report["policy"] == BUNDLED_FIXTURE_POLICY, profile_id
        assert len(evidence.positive_fixtures) >= 3, profile_id
        assert len(evidence.negative_fixtures) >= 3, profile_id
        negative_names = {fixture.name for fixture in evidence.negative_fixtures}
        assert "wrong positive field fingerprint" in negative_names, profile_id
        for invariant in profile["invariants"]:
            fields = {
                str(value)
                for value in [
                    *(invariant.get("fields") or []),
                    invariant.get("field"),
                ]
                if value
            }
            is_identity_only = invariant["rule"] in {
                "required_nonempty",
                "required_non_blank",
            } and fields <= set(profile["identity"]["canonical_key"])
            if not is_identity_only:
                assert f"rejects invariant {invariant['id']}" in negative_names, profile_id
        registry_evidence = {
            "profile_id": profile_id,
            "version": 1,
            "content_hash": enterprise_profile_content_hash(profile),
            "status": "validation",
            "adapter_id": profile["adapter"],
            "adapter_status": "available",
        }
        for fixture in evidence.positive_fixtures:
            result = execute_enterprise_profile(
                profile,
                fixture.payload,
                context=fixture.context,
                registry_evidence=registry_evidence,
            )
            assert result["records_written"] == fixture.expected_record_count, (
                profile_id,
                fixture.name,
            )
            assert result["headers"] == fixture.expected_headers, profile_id
            assert result["canonical"]["records"] == fixture.expected_records, profile_id
            assert result["rows"] == fixture.expected_rows, profile_id
        for fixture in evidence.negative_fixtures:
            assert fixture.expected_error_code, (profile_id, fixture.name)
            with pytest.raises(MappingError) as exc_info:
                execute_enterprise_profile(
                    profile,
                    fixture.payload,
                    context=fixture.context,
                    registry_evidence=registry_evidence,
                )
            assert exc_info.value.code == fixture.expected_error_code, (
                profile_id,
                fixture.name,
            )
