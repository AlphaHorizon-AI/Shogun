"""Deterministic canonical-entity transformations for structured enterprise data.

Profiles are data, not executable instructions.  This module implements the
small, intentionally bounded adapter used by API, OData, REST, JSON, CSV and
tabular record sets. The adapter also supports explicitly declared response
wrappers, header/line expansion, bounded heterogeneous unions, and a small set
of deterministic reconciliation rules. It never guesses collections or joins.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from shogun.mapping.errors import (
    MappingFieldMissing,
    MappingInputError,
    MappingSchemaError,
    MappingTransformationError,
    MappingTypeError,
)

CANONICAL_ENTITY_ADAPTER = "canonical_entity_map_v1"
SECTIONED_MATRIX_ADAPTER = "sectioned_record_matrix_v1"
_MISSING = object()
_PROFILE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,254}$")
_PATH_RE = re.compile(r"^[A-Za-z0-9_@:$-]+(?:\.[A-Za-z0-9_@:$-]+)*$")
_LIFECYCLE_STATES = {"candidate", "validated", "active", "bundled", "retired"}
_ADAPTER_REQUIREMENT_STATES = {"available", "planned", "unavailable", "disabled", "error"}
_IDENTITY_POLICIES = {"allow", "error", "skip", "replace", "merge"}
_SUPPORTED_FIELD_TYPES = {
    "any",
    "string",
    "integer",
    "number",
    "decimal",
    "boolean",
    "date",
    "datetime",
    "currency",
    "id",
    "array",
    "object",
}
_SUPPORTED_TRANSFORMS = {
    "none",
    "trim",
    "uppercase",
    "lowercase",
    "strip_leading_zero",
    "replace",
    "number_normalize",
    "decimal_normalize",
    "date_normalize",
    "datetime_normalize",
}
_SUPPORTED_INVARIANTS = {
    "none",
    "required_nonempty",
    "required_non_blank",
    "required_fields_present",
    "unique_composite",
    "nonnegative",
    "equals",
    "greater_than",
    "mutually_exclusive_nonzero",
    "header_equals_line_sum_with_tolerance",
    "debits_equal_credits",
    "sum_equals",
}
_FORBIDDEN_MANIFEST_KEYS = {
    "access_token",
    "api_key",
    "authorization",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "tenant_url",
}


def registered_transformation_adapters() -> dict[str, dict[str, Any]]:
    """Return executable deterministic adapters and their capabilities."""

    return {
        SECTIONED_MATRIX_ADAPTER: {
            "version": 1,
            "status": "available",
            "input_kinds": ["text", "pdf_text"],
            "capabilities": ["sections", "records", "deduplication", "planning_months"],
        },
        CANONICAL_ENTITY_ADAPTER: {
            "version": 2,
            "status": "available",
            "input_kinds": ["object", "array", "json", "tabular_records"],
            "capabilities": [
                "field_mapping",
                "aliases",
                "type_conversion",
                "deduplication",
                "canonical_envelope",
                "lineage",
                "nested_paths",
                "selection_fingerprints",
                "basic_invariants",
                "invariant_validation",
                "formula_neutralization",
                "declared_record_path",
                "paginated_wrapper_merge",
                "nested_collection_flattening",
                "synthetic_line_index",
                "heterogeneous_object_union",
                "business_rule:required_non_blank",
                "business_rule:unique_composite",
                "business_rule:required_fields_present",
                "business_rule:greater_than",
                "business_rule:mutually_exclusive_nonzero",
                "business_rule:header_equals_line_sum_with_tolerance",
                "business_rule:debits_equal_credits",
                "business_rule:sum_equals",
            ],
        },
    }


def _manifest_text(value: Any, *, field: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise MappingSchemaError(f"Manifest field '{field}' must be a string", field=field)
    normalized = value.strip()
    if not normalized:
        raise MappingSchemaError(f"Manifest field '{field}' cannot be blank", field=field)
    if len(normalized) > max_length:
        raise MappingSchemaError(
            f"Manifest field '{field}' exceeds {max_length} characters", field=field
        )
    return normalized


def _manifest_path(value: Any, *, field: str) -> str:
    path = _manifest_text(value, field=field, max_length=500)
    if not _PATH_RE.fullmatch(path):
        raise MappingSchemaError(
            f"Manifest field '{field}' must be a dotted field path", field=field
        )
    return path


def _manifest_string_list(value: Any, *, field: str, paths: bool) -> list[str]:
    if not isinstance(value, list):
        raise MappingSchemaError(f"Manifest field '{field}' must be a list", field=field)
    normalized: list[str] = []
    for index, item in enumerate(value):
        item_field = f"{field}.{index}"
        normalized.append(
            _manifest_path(item, field=item_field)
            if paths
            else _manifest_text(item, field=item_field, max_length=1000)
        )
    return normalized


def _manifest_identity_keys(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        raise MappingSchemaError(f"Manifest field '{field}' must be a list", field=field)
    normalized: list[str] = []
    for index, item in enumerate(value):
        item_field = f"{field}.{index}"
        if isinstance(item, dict):
            if set(item) != {"field"}:
                raise MappingSchemaError(
                    "Identity key objects may only contain a field property", field=item_field
                )
            item = item.get("field")
        normalized.append(_manifest_path(item, field=item_field))
    if len(normalized) != len(set(normalized)):
        raise MappingSchemaError("Identity key fields must be unique", field=field)
    return normalized


def _validated_transform_name(value: Any, *, field: str) -> str:
    if isinstance(value, str):
        return _manifest_text(value, field=field, max_length=100).lower()
    if not isinstance(value, dict):
        raise MappingSchemaError(
            "Profile transforms must be strings or objects", field=field
        )
    unknown = set(value) - {"name", "type", "options"}
    if unknown:
        raise MappingSchemaError(
            f"Profile transform contains unsupported properties: {', '.join(sorted(unknown))}",
            field=field,
        )
    raw_name = value.get("name")
    raw_type = value.get("type")
    if raw_name is not None and raw_type is not None and raw_name != raw_type:
        raise MappingSchemaError("Profile transform name and type must match", field=field)
    name = _manifest_text(raw_name or raw_type, field=field, max_length=100).lower()
    options = value.get("options", {})
    if not isinstance(options, dict):
        raise MappingSchemaError("Profile transform options must be an object", field=field)
    return name


def _parse_fingerprint(
    fingerprint: str,
    *,
    field: str = "selection.fingerprint",
) -> tuple[str, str, bool, str | None]:
    """Parse a bounded fingerprint into kind, value/path, equality flag, expected value."""

    value = _manifest_text(fingerprint, field=field, max_length=1000)
    kind = "field"
    expression = value
    if ":" in value:
        prefix, expression = value.split(":", 1)
        kind = prefix.strip().casefold()
        if kind not in {"object", "transport", "field", "path"}:
            raise MappingSchemaError(
                f"Unsupported fingerprint operator '{prefix.strip()}'", field=field
            )
        expression = expression.strip()
    if kind in {"object", "transport"}:
        if not expression or "=" in expression:
            raise MappingSchemaError(
                f"Fingerprint '{kind}:' requires one literal value", field=field
            )
        return kind, expression, False, None

    path, separator, expected = expression.partition("=")
    if separator and ":" not in value:
        raise MappingSchemaError(
            "Value fingerprints must use the explicit field: or path: prefix", field=field
        )
    path = _manifest_path(path.strip(), field=field)
    if separator and not expected.strip():
        raise MappingSchemaError("Fingerprint expected values cannot be blank", field=field)
    return "field", path, bool(separator), expected.strip() if separator else None


def validate_enterprise_profile_manifest(profile: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a declarative enterprise profile manifest.

    Validation is deliberately independent of adapter availability so planned
    profiles can be catalogued. Execution performs the additional availability
    and lifecycle checks.
    """

    if not isinstance(profile, dict):
        raise MappingSchemaError("Transformation profile must be an object")
    profile = deepcopy(profile)
    profile_id = _manifest_text(profile.get("id"), field="id", max_length=255)
    if not _PROFILE_ID_RE.fullmatch(profile_id):
        raise MappingSchemaError("Transformation profile has an invalid id", field="id")
    profile["id"] = profile_id
    version = profile.get("version")
    if isinstance(version, bool) or not isinstance(version, (str, int)):
        raise MappingSchemaError("Transformation profile version must be a string or integer", field="version")
    version_text = str(version).strip()
    if not version_text or len(version_text) > 100:
        raise MappingSchemaError("Transformation profile requires a valid version", field="version")
    profile["version"] = version_text
    if _contains_forbidden_manifest_key(profile):
        raise MappingSchemaError("Transformation profiles cannot contain credentials or tenant URLs")

    platform = profile.get("platform")
    if not isinstance(platform, dict):
        raise MappingSchemaError(
            "Transformation profile requires platform vendor, product, and family",
            field="platform",
        )
    for key in ("vendor", "product", "family"):
        platform[key] = _manifest_text(platform.get(key), field=f"platform.{key}", max_length=255)

    source = profile.get("source")
    if not isinstance(source, dict):
        raise MappingSchemaError("Transformation profile requires a source transport", field="source")
    source["transport"] = _manifest_text(
        source.get("transport"), field="source.transport", max_length=255
    )
    if source.get("record_path") is not None:
        record_path = _manifest_path(source.get("record_path"), field="source.record_path")
        source["record_path"] = record_path
    if source.get("record_shape") is not None:
        source["record_shape"] = _manifest_text(
            source.get("record_shape"), field="source.record_shape", max_length=100
        ).lower()
    related_objects = _manifest_string_list(
        source.get("related_objects", []),
        field="source.related_objects",
        paths=True,
    )
    source["related_objects"] = related_objects
    union_paths = _manifest_string_list(
        source.get("union_paths", []),
        field="source.union_paths",
        paths=True,
    )
    source["union_paths"] = union_paths
    if source.get("union_discriminator") is not None:
        source["union_discriminator"] = _manifest_path(
            source.get("union_discriminator"),
            field="source.union_discriminator",
        )

    contract = profile.get("canonical_contract")
    if not isinstance(contract, dict):
        raise MappingSchemaError(
            "Transformation profile requires a canonical contract id, version, and record kind",
            field="canonical_contract",
        )
    contract["id"] = _manifest_text(
        contract.get("id"), field="canonical_contract.id", max_length=255
    )
    contract_version = contract.get("version")
    if isinstance(contract_version, bool) or not isinstance(contract_version, (str, int)):
        raise MappingSchemaError(
            "Canonical contract version must be a string or integer",
            field="canonical_contract.version",
        )
    contract["version"] = _manifest_text(
        str(contract_version), field="canonical_contract.version", max_length=100
    )
    contract["record_kind"] = _manifest_text(
        contract.get("record_kind"), field="canonical_contract.record_kind", max_length=255
    )

    adapter_requirements = profile.get("adapter_requirements")
    if adapter_requirements is None:
        adapter_requirements = {}
    elif not isinstance(adapter_requirements, dict):
        raise MappingSchemaError(
            "Transformation profile adapter_requirements must be an object",
            field="adapter_requirements",
        )
    top_level_adapter = profile.get("adapter")
    required_adapter = adapter_requirements.get("adapter")
    if top_level_adapter is not None and required_adapter is not None:
        if not isinstance(top_level_adapter, str) or not isinstance(required_adapter, str):
            raise MappingSchemaError("Transformation adapter ids must be strings", field="adapter")
        if top_level_adapter.strip() != required_adapter.strip():
            raise MappingSchemaError(
                "Top-level and required transformation adapter ids must match",
                field="adapter_requirements.adapter",
            )
    adapter = _manifest_text(
        top_level_adapter or required_adapter,
        field="adapter",
        max_length=255,
    )
    if not _PROFILE_ID_RE.fullmatch(adapter):
        raise MappingSchemaError("Transformation profile has an invalid adapter id", field="adapter")
    adapter_requirements["adapter"] = adapter
    minimum_version = adapter_requirements.get("minimum_version", 1)
    if isinstance(minimum_version, bool) or not isinstance(minimum_version, int) or minimum_version < 1:
        raise MappingSchemaError(
            "adapter_requirements.minimum_version must be a positive integer",
            field="adapter_requirements.minimum_version",
        )
    adapter_requirements["minimum_version"] = minimum_version
    requirement_status = _manifest_text(
        adapter_requirements.get("status", "planned"),
        field="adapter_requirements.status",
        max_length=30,
    ).lower()
    if requirement_status not in _ADAPTER_REQUIREMENT_STATES:
        raise MappingSchemaError(
            f"Unsupported adapter requirement status '{requirement_status}'",
            field="adapter_requirements.status",
        )
    adapter_requirements["status"] = requirement_status
    capabilities = _manifest_string_list(
        adapter_requirements.get("capabilities", []),
        field="adapter_requirements.capabilities",
        paths=False,
    )
    if len(capabilities) != len(set(capabilities)):
        raise MappingSchemaError(
            "Transformation adapter capabilities must be unique",
            field="adapter_requirements.capabilities",
        )
    adapter_requirements["capabilities"] = capabilities
    fail_closed = adapter_requirements.get("fail_closed", True)
    if not isinstance(fail_closed, bool):
        raise MappingSchemaError(
            "adapter_requirements.fail_closed must be a boolean",
            field="adapter_requirements.fail_closed",
        )
    adapter_requirements["fail_closed"] = fail_closed
    profile["adapter"] = adapter
    profile["adapter_requirements"] = adapter_requirements

    parameters = profile.get("parameters", {})
    if not isinstance(parameters, dict):
        raise MappingSchemaError("Transformation profile parameters must be an object", field="parameters")
    profile["parameters"] = parameters
    manifest_version = profile.get("manifest_version", 1)
    if isinstance(manifest_version, bool) or not isinstance(manifest_version, (str, int)):
        raise MappingSchemaError("manifest_version must be a string or integer", field="manifest_version")
    profile["manifest_version"] = str(manifest_version).strip()
    lifecycle = _manifest_text(
        profile.get("lifecycle", "candidate"), field="lifecycle", max_length=30
    ).lower()
    if lifecycle not in _LIFECYCLE_STATES:
        raise MappingSchemaError(f"Unsupported transformation profile lifecycle '{lifecycle}'", field="lifecycle")
    profile["lifecycle"] = lifecycle
    profile["profile_kind"] = _manifest_text(
        profile.get("profile_kind", "structured_ingress"), field="profile_kind", max_length=100
    )
    model_fallback = profile.get("model_fallback", False)
    if not isinstance(model_fallback, bool):
        raise MappingSchemaError("model_fallback must be a boolean", field="model_fallback")
    profile["model_fallback"] = model_fallback

    field_map = profile.get("field_map")
    if not isinstance(field_map, list) or not field_map:
        raise MappingSchemaError("Transformation profile requires at least one field mapping", field="field_map")
    if len(field_map) > 500:
        raise MappingSchemaError("Transformation profile exceeds 500 field mappings", field="field_map")
    seen_targets: set[str] = set()
    for index, raw_rule in enumerate(field_map):
        if not isinstance(raw_rule, dict):
            raise MappingSchemaError(
                "Transformation profile field mappings must be objects",
                field=f"field_map.{index}",
            )
        source_path = _manifest_path(raw_rule.get("source"), field=f"field_map.{index}.source")
        target_path = _manifest_path(raw_rule.get("target"), field=f"field_map.{index}.target")
        if target_path in seen_targets:
            raise MappingSchemaError("Transformation profile targets must be unique", field=target_path)
        if any(
            target_path.startswith(f"{existing}.") or existing.startswith(f"{target_path}.")
            for existing in seen_targets
        ):
            raise MappingSchemaError(
                "Transformation profile target paths cannot overlap scalar and nested values",
                field=target_path,
            )
        seen_targets.add(target_path)
        raw_rule["source"] = source_path
        raw_rule["target"] = target_path
        field_type = _manifest_text(
            raw_rule.get("type", "any"), field=f"field_map.{index}.type", max_length=50
        ).lower()
        if requirement_status == "available" and field_type not in _SUPPORTED_FIELD_TYPES:
            raise MappingSchemaError(
                f"Available adapter '{adapter}' does not support field type '{field_type}'",
                field=f"field_map.{index}.type",
            )
        raw_rule["type"] = field_type
        required = raw_rule.get("required", False)
        if not isinstance(required, bool):
            raise MappingSchemaError(
                "Field mapping required must be a boolean", field=f"field_map.{index}.required"
            )
        raw_rule["required"] = required
        raw_rule["aliases"] = _manifest_string_list(
            raw_rule.get("aliases", []), field=f"field_map.{index}.aliases", paths=True
        )
        transforms = raw_rule.get("transforms", [])
        if not isinstance(transforms, list):
            raise MappingSchemaError(
                "Field mapping transforms must be a list", field=f"field_map.{index}.transforms"
            )
        for transform_index, transform in enumerate(transforms):
            transform_name = _validated_transform_name(
                transform, field=f"field_map.{index}.transforms.{transform_index}"
            )
            if requirement_status == "available" and transform_name not in _SUPPORTED_TRANSFORMS:
                raise MappingSchemaError(
                    f"Available adapter '{adapter}' does not support transform '{transform_name}'",
                    field=f"field_map.{index}.transforms.{transform_index}",
                )
        raw_rule["transforms"] = transforms

    identity = profile.get("identity")
    if identity is None:
        identity = {}
    elif not isinstance(identity, dict):
        raise MappingSchemaError("Transformation profile identity must be an object", field="identity")
    identity["source_key"] = _manifest_identity_keys(
        identity.get("source_key", []), field="identity.source_key"
    )
    identity["canonical_key"] = _manifest_identity_keys(
        identity.get("canonical_key", []), field="identity.canonical_key"
    )
    if identity["source_key"] and identity["canonical_key"] and (
        len(identity["source_key"]) != len(identity["canonical_key"])
    ):
        raise MappingSchemaError(
            "Source and canonical identity keys must have the same length", field="identity"
        )
    unknown_identity_targets = set(identity["canonical_key"]) - seen_targets
    if unknown_identity_targets:
        raise MappingSchemaError(
            "Canonical identity keys must reference mapped target fields",
            field=sorted(unknown_identity_targets)[0],
        )
    conflict_policy = _manifest_text(
        identity.get("conflict_policy", "error"),
        field="identity.conflict_policy",
        max_length=30,
    ).lower()
    if conflict_policy not in _IDENTITY_POLICIES:
        raise MappingSchemaError("Unsupported identity conflict policy", field="identity.conflict_policy")
    identity["conflict_policy"] = conflict_policy
    profile["identity"] = identity

    selection = profile.get("selection")
    if selection is None:
        selection = {}
    elif not isinstance(selection, dict):
        raise MappingSchemaError("Transformation profile selection must be an object", field="selection")
    positives = _manifest_string_list(
        selection.get("positive_fingerprints", []),
        field="selection.positive_fingerprints",
        paths=False,
    )
    negatives = _manifest_string_list(
        selection.get("negative_fingerprints", []),
        field="selection.negative_fingerprints",
        paths=False,
    )
    for fingerprint_index, fingerprint in enumerate(positives):
        _parse_fingerprint(fingerprint, field=f"selection.positive_fingerprints.{fingerprint_index}")
    for fingerprint_index, fingerprint in enumerate(negatives):
        _parse_fingerprint(fingerprint, field=f"selection.negative_fingerprints.{fingerprint_index}")
    if {value.casefold() for value in positives} & {value.casefold() for value in negatives}:
        raise MappingSchemaError("Positive and negative profile fingerprints must not overlap")
    selection["positive_fingerprints"] = positives
    selection["negative_fingerprints"] = negatives
    profile["selection"] = selection

    privacy = profile.get("privacy")
    if privacy is None:
        privacy = {}
    elif not isinstance(privacy, dict):
        raise MappingSchemaError("Transformation profile privacy must be an object", field="privacy")
    privacy["classification"] = _manifest_text(
        privacy.get("classification", "internal"), field="privacy.classification", max_length=50
    )
    privacy["pii_fields"] = _manifest_string_list(
        privacy.get("pii_fields", []), field="privacy.pii_fields", paths=True
    )
    privacy["secret_fields"] = _manifest_string_list(
        privacy.get("secret_fields", []), field="privacy.secret_fields", paths=True
    )
    privacy["retention"] = _manifest_text(
        privacy.get("retention", "flow_policy"), field="privacy.retention", max_length=100
    )
    profile["privacy"] = privacy

    invariants = profile.get("invariants", [])
    if not isinstance(invariants, list):
        raise MappingSchemaError("Transformation profile invariants must be a list", field="invariants")
    for invariant_index, invariant in enumerate(invariants):
        if not isinstance(invariant, dict):
            raise MappingSchemaError(
                "Profile invariants must be objects", field=f"invariants.{invariant_index}"
            )
        rule = _manifest_text(
            invariant.get("rule", "none"), field=f"invariants.{invariant_index}.rule", max_length=100
        ).lower()
        if requirement_status == "available" and rule not in _SUPPORTED_INVARIANTS:
            raise MappingSchemaError(
                f"Available adapter '{adapter}' does not support invariant '{rule}'",
                field=f"invariants.{invariant_index}.rule",
            )
        invariant["rule"] = rule
        fields = _manifest_string_list(
            invariant.get("fields", []), field=f"invariants.{invariant_index}.fields", paths=True
        )
        if invariant.get("field") is not None:
            fields.append(_manifest_path(invariant.get("field"), field=f"invariants.{invariant_index}.field"))
            invariant.pop("field", None)
        if rule not in {"none", ""} and not fields:
            raise MappingSchemaError(
                "Executable invariants require at least one canonical field",
                field=f"invariants.{invariant_index}.fields",
            )
        if rule == "equals" and "value" not in invariant:
            raise MappingSchemaError(
                "The equals invariant requires a value", field=f"invariants.{invariant_index}.value"
            )
        unknown_targets = set(fields) - seen_targets
        if unknown_targets:
            raise MappingSchemaError(
                "Invariant fields must reference mapped canonical targets",
                field=sorted(unknown_targets)[0],
            )
        expected_field_counts = {
            "greater_than": 1,
            "mutually_exclusive_nonzero": 2,
            "header_equals_line_sum_with_tolerance": 2,
            "debits_equal_credits": 2,
            "sum_equals": 1,
        }
        expected_field_count = expected_field_counts.get(rule)
        if expected_field_count is not None and len(fields) != expected_field_count:
            raise MappingSchemaError(
                f"Invariant '{rule}' requires exactly {expected_field_count} field(s)",
                field=f"invariants.{invariant_index}.fields",
            )
        if rule in {"greater_than", "sum_equals"} and "value" not in invariant:
            raise MappingSchemaError(
                f"Invariant '{rule}' requires a comparison value",
                field=f"invariants.{invariant_index}.value",
            )
        invariant["fields"] = list(dict.fromkeys(fields))
    profile["invariants"] = invariants

    if requirement_status == "available":
        registered = registered_transformation_adapters().get(adapter)
        if not registered or str(registered.get("status") or "").lower() != "available":
            raise MappingSchemaError(
                f"Transformation profile requires unavailable adapter '{adapter}'", field="adapter"
            )
        runtime_version = registered.get("version")
        if isinstance(runtime_version, bool) or not isinstance(runtime_version, int):
            raise MappingSchemaError(
                f"Registered adapter '{adapter}' has an invalid runtime version", field="adapter"
            )
        if runtime_version < minimum_version:
            raise MappingSchemaError(
                f"Transformation profile requires adapter '{adapter}' version {minimum_version}, "
                f"but runtime version is {runtime_version}",
                field="adapter_requirements.minimum_version",
            )
        runtime_capabilities = {
            str(capability) for capability in registered.get("capabilities") or []
        }
        unsupported_capabilities = sorted(set(capabilities) - runtime_capabilities)
        if unsupported_capabilities:
            raise MappingSchemaError(
                f"Transformation profile requires unsupported adapter capabilities: "
                f"{', '.join(unsupported_capabilities)}",
                field="adapter_requirements.capabilities",
            )
        record_shape = str(source.get("record_shape") or "").lower()
        capability_set = set(capabilities)
        if "nested_collection_flattening" in capability_set:
            if record_shape != "header_with_lines" or len(related_objects) != 1:
                raise MappingSchemaError(
                    "Nested collection flattening requires header_with_lines and exactly one "
                    "declared related object path",
                    field="source.related_objects",
                )
        if "synthetic_line_index" in capability_set and (
            "nested_collection_flattening" not in capability_set
        ):
            raise MappingSchemaError(
                "Synthetic line indexes require nested collection flattening",
                field="adapter_requirements.capabilities",
            )
        if "heterogeneous_object_union" in capability_set:
            if record_shape != "collection" or len(union_paths) < 2:
                raise MappingSchemaError(
                    "Heterogeneous unions require a collection shape and at least two "
                    "declared union paths",
                    field="source.union_paths",
                )
            if not source.get("union_discriminator"):
                raise MappingSchemaError(
                    "Heterogeneous unions require a discriminator field",
                    field="source.union_discriminator",
                )
        if not fail_closed:
            raise MappingSchemaError(
                "Executable transformation profiles must fail closed",
                field="adapter_requirements.fail_closed",
            )
    return profile


def execute_enterprise_profile(
    profile: dict[str, Any],
    payload: Any,
    *,
    context: dict[str, Any] | None = None,
    registry_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map a structured payload into a canonical envelope and table rows."""

    source_content_hash = enterprise_profile_content_hash(profile)
    manifest = validate_enterprise_profile_manifest(profile)
    adapter = manifest["adapter"]
    registered = registered_transformation_adapters().get(adapter)
    evidence = _validate_registry_evidence(
        manifest,
        registry_evidence,
        source_content_hash=source_content_hash,
    )
    declared_status = str(manifest["adapter_requirements"].get("status") or "planned").lower()
    if (
        declared_status != "available"
        or not registered
        or registered.get("status") != "available"
    ):
        raise MappingSchemaError(
            f"Transformation profile '{manifest['id']}' requires unavailable adapter '{adapter}'",
            field="adapter",
        )
    if adapter != CANONICAL_ENTITY_ADAPTER:
        raise MappingSchemaError(
            f"Adapter '{adapter}' is not a structured canonical-entity adapter",
            field="adapter",
        )

    parsed = _parse_payload(payload)
    records, source_locations = _records_from_payload(parsed, manifest)
    if not records:
        raise MappingInputError("Transformation profile input contained no records")
    _validate_selection_fingerprints(manifest, records)

    mapped: list[dict[str, Any]] = []
    rows: list[list[Any]] = []
    lineage: list[dict[str, Any]] = []
    for index, (record, source_location) in enumerate(
        zip(records, source_locations, strict=True)
    ):
        source_identity_keys = manifest["identity"].get("source_key") or []
        source_identity = _identity_value(record, source_identity_keys)
        if source_identity_keys and source_identity is None:
            raise MappingFieldMissing(
                "Source identity fields must be present and non-blank",
                field=", ".join(str(key) for key in source_identity_keys),
                record_index=index,
            )
        canonical: dict[str, Any] = {}
        row: list[Any] = []
        for rule in manifest["field_map"]:
            value = _mapped_value(record, rule, index)
            _path_set(canonical, str(rule["target"]), value)
            row.append(_excel_safe(value))
        mapped.append(canonical)
        rows.append(row)
        lineage.append(
            {
                "record_index": index,
                "source_system": f"{manifest['platform']['vendor']}:{manifest['platform']['product']}",
                "source_object": manifest["source"].get("object"),
                "source_id": source_identity,
                **source_location,
                "flow_id": (context or {}).get("flow_id"),
                "node_id": (context or {}).get("node_id"),
                "source_node_id": (context or {}).get("source_node_id"),
            }
        )

    mapped, rows, lineage = _deduplicate(manifest, mapped, rows, lineage)
    _validate_invariants(manifest, mapped)
    contract = manifest["canonical_contract"]
    headers = [str(rule["target"]) for rule in manifest["field_map"]]
    return {
        "__shogun_mapping_output__": True,
        "__shogun_canonical_output__": True,
        "status": "SUCCESS",
        "type": "table",
        "rows": rows,
        "headers": headers,
        "canonical": {
            "contract": {"id": contract["id"], "version": contract["version"]},
            "record_kind": contract["record_kind"],
            "records": mapped,
        },
        "profile": {
            "id": manifest["id"],
            "version": manifest["version"],
            "adapter": adapter,
            "registry_version": evidence["version"],
            "content_hash": evidence["content_hash"],
        },
        "privacy": deepcopy(manifest["privacy"]),
        "records_received": len(records),
        "records_written": len(mapped),
        "records_failed": 0,
        "lineage": lineage,
    }


def enterprise_profile_content_hash(profile: dict[str, Any]) -> str:
    """Return the registry-compatible content hash for a profile definition."""

    encoded = json.dumps(
        profile,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_registry_evidence(
    manifest: dict[str, Any],
    evidence: dict[str, Any] | None,
    *,
    source_content_hash: str,
) -> dict[str, Any]:
    """Require server-created registry evidence instead of manifest self-claims."""

    if not isinstance(evidence, dict):
        raise MappingSchemaError(
            "Enterprise transformation profiles must be resolved through the governed registry",
            field="transformation_profile",
        )
    profile_id = str(evidence.get("profile_id") or "")
    adapter_id = str(evidence.get("adapter_id") or "")
    status = str(evidence.get("status") or "").lower()
    adapter_status = str(evidence.get("adapter_status") or "").lower()
    version = evidence.get("version")
    content_hash = str(evidence.get("content_hash") or "")
    if profile_id != manifest["id"] or adapter_id != manifest["adapter"]:
        raise MappingSchemaError("Transformation profile registry evidence does not match the manifest")
    private_evidence = (
        status == "private_validated"
        and str(evidence.get("source") or "").lower() == "private_file"
        and evidence.get("server_validated") is True
    )
    if (
        status not in {"active", "validation"}
        and not private_evidence
    ) or adapter_status != "available":
        raise MappingSchemaError(
            "Transformation profile is not active or privately validated with an available adapter"
        )
    if not isinstance(version, int) or version < 1:
        raise MappingSchemaError("Transformation profile registry version is invalid")
    if content_hash != source_content_hash:
        raise MappingSchemaError("Transformation profile content hash does not match the registry")
    return evidence


def _contains_forbidden_manifest_key(value: Any) -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).casefold()).strip("_")
            if normalized in _FORBIDDEN_MANIFEST_KEYS or _contains_forbidden_manifest_key(child):
                return True
    elif isinstance(value, list):
        return any(_contains_forbidden_manifest_key(item) for item in value)
    return False


def _parse_payload(payload: Any) -> Any:
    if not isinstance(payload, str):
        return deepcopy(payload)
    text = payload.strip()
    if not text:
        raise MappingInputError("Transformation profile input is empty")
    if text.startswith("```") and text.endswith("```"):
        fenced_body = text[3:-3].strip()
        if fenced_body[:4].casefold() == "json" and (
            len(fenced_body) == 4 or fenced_body[4].isspace()
        ):
            fenced_body = fenced_body[4:].lstrip()
        text = fenced_body
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise MappingInputError("Transformation profile input is not valid JSON") from exc


def _records_from_payload(
    payload: Any,
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve only manifest-declared wrappers, unions, and header/line joins."""

    source = manifest.get("source") or {}
    capabilities = set(
        (manifest.get("adapter_requirements") or {}).get("capabilities") or []
    )
    if "heterogeneous_object_union" in capabilities:
        records, locations = _heterogeneous_union_records(payload, source)
    else:
        records, locations = _declared_wrapper_records(payload, source)
    if "nested_collection_flattening" in capabilities:
        records, locations = _flatten_header_lines(
            records,
            locations,
            source,
            manifest,
        )
    return records, locations


def _declared_wrapper_records(
    payload: Any,
    source: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Resolve a declared record path, including an explicit list of page wrappers."""

    record_path = str(source.get("record_path") or "").strip()
    if record_path and isinstance(payload, list):
        pages = payload
    else:
        pages = [payload]

    records: list[dict[str, Any]] = []
    locations: list[dict[str, Any]] = []
    for page_index, page in enumerate(pages):
        data = _path_get(page, record_path) if record_path else page
        if data is _MISSING:
            raise MappingInputError(
                f"Configured source record path '{record_path}' was not found",
                field=record_path,
            )
        page_records = _record_collection(data, label=record_path or "payload")
        for record_index, record in enumerate(page_records):
            records.append(deepcopy(record))
            locations.append(
                {
                    "page_index": page_index,
                    "source_record_index": record_index,
                }
            )
    return records, locations


def _heterogeneous_union_records(
    payload: Any,
    source: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Union explicitly listed collections and stamp a bounded discriminator."""

    union_paths = [str(value) for value in source.get("union_paths") or []]
    discriminator = str(source.get("union_discriminator") or "").strip()
    if not union_paths or not discriminator:
        raise MappingSchemaError(
            "Heterogeneous union source configuration is incomplete",
            field="source.union_paths",
        )

    # Already-normalized arrays remain valid only when every item carries the
    # declared discriminator. Otherwise a list is treated as page wrappers.
    if isinstance(payload, list) and payload and all(isinstance(item, dict) for item in payload):
        if all(_path_get(item, discriminator) is not _MISSING for item in payload):
            return (
                [deepcopy(item) for item in payload],
                [
                    {"page_index": 0, "source_record_index": index}
                    for index in range(len(payload))
                ],
            )
        pages = payload
    else:
        pages = [payload]

    records: list[dict[str, Any]] = []
    locations: list[dict[str, Any]] = []
    for page_index, page in enumerate(pages):
        if not isinstance(page, dict):
            raise MappingInputError("Heterogeneous union pages must be objects")
        for union_path in union_paths:
            selected = _path_get(page, union_path)
            if selected is _MISSING:
                continue
            discriminator_value = union_path.rsplit(".", 1)[-1]
            for record_index, raw_record in enumerate(
                _record_collection(selected, label=union_path)
            ):
                record = deepcopy(raw_record)
                existing = _path_get(record, discriminator)
                if existing is _MISSING:
                    _path_set(record, discriminator, discriminator_value)
                elif str(existing).casefold() != discriminator_value.casefold():
                    raise MappingInputError(
                        f"Union discriminator '{discriminator}' conflicts with path "
                        f"'{union_path}'",
                        field=discriminator,
                    )
                records.append(record)
                locations.append(
                    {
                        "page_index": page_index,
                        "source_record_index": record_index,
                        "union_path": union_path,
                    }
                )
    if not records:
        raise MappingInputError("None of the declared heterogeneous union paths contained records")
    return records, locations


def _record_collection(value: Any, *, label: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise MappingInputError(
            f"Transformation profile path '{label}' must resolve to an object or array of objects",
            field=label,
        )
    return list(value)


def _flatten_header_lines(
    headers: list[dict[str, Any]],
    locations: list[dict[str, Any]],
    source: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    related_objects = [str(value) for value in source.get("related_objects") or []]
    if len(related_objects) != 1:
        raise MappingSchemaError(
            "Header/line execution requires exactly one related object path",
            field="source.related_objects",
        )
    related_path = related_objects[0]
    declared_paths = {
        str(value)
        for value in [
            *(manifest.get("identity") or {}).get("source_key", []),
            *[
                rule.get("source")
                for rule in manifest.get("field_map") or []
                if isinstance(rule, dict)
            ],
            *[
                alias
                for rule in manifest.get("field_map") or []
                if isinstance(rule, dict)
                for alias in rule.get("aliases") or []
            ],
        ]
        if value
    }
    flattened: list[dict[str, Any]] = []
    flattened_locations: list[dict[str, Any]] = []
    wrapper_names = ("items", "value", "records", "collection", "result")
    for header_index, (header, location) in enumerate(
        zip(headers, locations, strict=True)
    ):
        raw_lines = _path_get(header, related_path)
        if raw_lines is _MISSING:
            raise MappingInputError(
                f"Declared related object path '{related_path}' was not found",
                field=related_path,
                record_index=header_index,
            )
        target_path = related_path
        if isinstance(raw_lines, dict):
            candidates = [
                name for name in wrapper_names if isinstance(raw_lines.get(name), list)
            ]
            if len(candidates) != 1:
                raise MappingInputError(
                    f"Related object path '{related_path}' must contain exactly one "
                    "recognized collection wrapper",
                    field=related_path,
                    record_index=header_index,
                )
            wrapper = candidates[0]
            raw_lines = raw_lines[wrapper]
            wrapped_path = f"{related_path}.{wrapper}"
            if any(path.startswith(f"{wrapped_path}.") for path in declared_paths):
                target_path = wrapped_path
        lines = _record_collection(raw_lines, label=related_path)
        for line_index, raw_line in enumerate(lines):
            line = deepcopy(raw_line)
            line.setdefault("_index", line_index)
            flattened_record = deepcopy(header)
            _path_set(flattened_record, target_path, line)
            flattened.append(flattened_record)
            flattened_locations.append(
                {
                    **location,
                    "header_index": header_index,
                    "line_index": line_index,
                    "related_object_path": related_path,
                }
            )
    return flattened, flattened_locations


def _mapped_value(record: dict[str, Any], rule: dict[str, Any], index: int) -> Any:
    paths = [str(rule["source"]), *[str(value) for value in rule.get("aliases") or []]]
    value = _MISSING
    for path in paths:
        value = _path_get(record, path)
        if value is not _MISSING:
            break
    if value is _MISSING:
        if "default" in rule:
            value = deepcopy(rule.get("default"))
        elif rule.get("required"):
            raise MappingFieldMissing(
                f"Required source field '{rule['source']}' was not found",
                field=str(rule["source"]),
                record_index=index,
            )
        else:
            return None
    try:
        for transform in rule.get("transforms") or []:
            value = _apply_transform(value, transform)
        return _coerce(value, str(rule.get("type") or "any"), str(rule["source"]), index)
    except (MappingFieldMissing, MappingTypeError, MappingTransformationError):
        raise
    except Exception as exc:
        raise MappingTransformationError(
            f"Transformation failed for source field '{rule['source']}'",
            field=str(rule["source"]),
            record_index=index,
        ) from exc


def _apply_transform(value: Any, raw_transform: Any) -> Any:
    if isinstance(raw_transform, str):
        name, options = raw_transform, {}
    elif isinstance(raw_transform, dict):
        name = str(raw_transform.get("name") or raw_transform.get("type") or "")
        options = dict(raw_transform.get("options") or {})
    else:
        raise MappingTransformationError("Profile transform must be a string or object")
    name = name.strip().lower()
    if name in {"", "none"}:
        return value
    if name == "trim":
        return value.strip() if isinstance(value, str) else value
    if name == "uppercase":
        return str(value).upper()
    if name == "lowercase":
        return str(value).lower()
    if name == "strip_leading_zero":
        return str(value).lstrip("0") or "0"
    if name == "replace":
        return str(value).replace(str(options.get("old", "")), str(options.get("new", "")))
    if name in {"number_normalize", "decimal_normalize"}:
        return _number(value)
    if name in {"date_normalize", "datetime_normalize"}:
        return _date_value(value, datetime_output=name.startswith("datetime"))
    raise MappingTransformationError(f"Unsupported enterprise profile transform '{name}'")


def _coerce(value: Any, expected: str, field: str, index: int) -> Any:
    expected = expected.strip().lower()
    if value is None or expected in {"", "any"}:
        return value
    try:
        if expected == "object":
            if not isinstance(value, dict):
                raise ValueError
            return value
        if expected == "array":
            if not isinstance(value, list):
                raise ValueError
            return value
        if expected in {"string", "currency", "id"}:
            return str(value)
        if expected == "integer":
            number = Decimal(str(_number(value)))
            if number != number.to_integral_value():
                raise InvalidOperation
            return int(number)
        if expected in {"number", "decimal"}:
            return _number(value)
        if expected == "boolean":
            if isinstance(value, bool):
                return value
            normalized = str(value).strip().casefold()
            if normalized in {"true", "yes", "1", "on"}:
                return True
            if normalized in {"false", "no", "0", "off"}:
                return False
            raise ValueError
        if expected == "date":
            return _date_value(value, datetime_output=False)
        if expected == "datetime":
            return _date_value(value, datetime_output=True)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MappingTypeError(
            f"Source field '{field}' could not be converted to {expected}",
            field=field,
            record_index=index,
            expected=expected,
            received=value,
        ) from exc
    raise MappingTypeError(
        f"Source field '{field}' declares unsupported type '{expected}'",
        field=field,
        record_index=index,
        expected=expected,
    )


def _number(value: Any) -> int | float:
    if isinstance(value, bool):
        raise InvalidOperation
    if isinstance(value, (int, float, Decimal)):
        number = Decimal(str(value))
    else:
        text = str(value).strip().replace("\u00a0", "").replace(" ", "")
        if "," in text and "." in text:
            text = (
                text.replace(".", "").replace(",", ".")
                if text.rfind(",") > text.rfind(".")
                else text.replace(",", "")
            )
        elif "," in text:
            text = text.replace(",", ".")
        number = Decimal(text)
    if not number.is_finite():
        raise InvalidOperation
    return int(number) if number == number.to_integral_value() else float(number)


def _date_value(value: Any, *, datetime_output: bool) -> str:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    else:
        text = str(value).strip()
        parsed = None
        for fmt in (
            "%Y-%m-%d",
            "%d.%m.%Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed.isoformat() if datetime_output else parsed.date().isoformat()


def _path_get(value: Any, path: str) -> Any:
    if not path:
        return value
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return _MISSING
    return current


def _validate_selection_fingerprints(
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
) -> None:
    """Fail closed when a profile is pointed at the wrong structured object.

    Fingerprints are intentionally small and non-executable:

    * ``field:path.to.value`` (or simply ``path.to.value``) requires a field.
    * ``field:path.to.value=Expected`` additionally requires an exact value.
    * ``object:ProductsV2`` and ``transport:odata`` bind manifest metadata.

    Every positive fingerprint must match; any negative match rejects the
    payload. Required field mappings remain the record-level completeness gate.
    """

    selection = manifest.get("selection") or {}
    for index, raw in enumerate(selection.get("positive_fingerprints") or []):
        fingerprint = str(raw).strip()
        if fingerprint and not _fingerprint_matches(
            fingerprint,
            manifest,
            records,
            require_all_records=True,
            field=f"selection.positive_fingerprints.{index}",
        ):
            raise MappingInputError(
                f"Input does not match positive fingerprint '{fingerprint}' for profile '{manifest['id']}'"
            )
    for index, raw in enumerate(selection.get("negative_fingerprints") or []):
        fingerprint = str(raw).strip()
        if fingerprint and _fingerprint_matches(
            fingerprint,
            manifest,
            records,
            require_all_records=False,
            field=f"selection.negative_fingerprints.{index}",
        ):
            raise MappingInputError(
                f"Input matches negative fingerprint '{fingerprint}' for profile '{manifest['id']}'"
            )


def _fingerprint_matches(
    fingerprint: str,
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    require_all_records: bool,
    field: str,
) -> bool:
    kind, expression, has_expected, expected = _parse_fingerprint(fingerprint, field=field)
    if kind == "object":
        return str((manifest.get("source") or {}).get("object") or "").casefold() == expression.casefold()
    if kind == "transport":
        return str((manifest.get("source") or {}).get("transport") or "").casefold() == expression.casefold()

    def record_matches(record: dict[str, Any]) -> bool:
        value = _path_get(record, expression)
        if value is _MISSING:
            return False
        return not has_expected or str(value).strip().casefold() == str(expected).casefold()

    matches = [record_matches(record) for record in records]
    return all(matches) if require_all_records else any(matches)


def _excel_safe(value: Any) -> Any:
    """Neutralize text that spreadsheet applications could execute as a formula."""

    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _path_set(target: dict[str, Any], path: str, value: Any) -> None:
    parts = [part for part in path.split(".") if part]
    if not parts:
        raise MappingSchemaError("Canonical target path cannot be empty")
    current = target
    for part in parts[:-1]:
        existing = current.get(part)
        if existing is None:
            existing = {}
            current[part] = existing
        if not isinstance(existing, dict):
            raise MappingSchemaError(f"Canonical target path '{path}' conflicts with a scalar value")
        current = existing
    current[parts[-1]] = value


def _identity_value(record: dict[str, Any], keys: list[Any]) -> str | None:
    if not keys:
        return None
    values: list[Any] = []
    for raw_key in keys:
        key = str(raw_key.get("field") if isinstance(raw_key, dict) else raw_key)
        value = _path_get(record, key)
        if value is _MISSING or _identity_component_is_blank(value):
            return None
        values.append(value)
    return json.dumps(values, sort_keys=True, default=str)


def _identity_component_is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _deduplicate(
    manifest: dict[str, Any],
    mapped: list[dict[str, Any]],
    rows: list[list[Any]],
    lineage: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[list[Any]], list[dict[str, Any]]]:
    keys = manifest["identity"].get("canonical_key") or []
    policy = manifest["identity"].get("conflict_policy", "error")
    if not keys:
        return mapped, rows, lineage
    markers: list[str] = []
    for record, source in zip(mapped, lineage, strict=True):
        marker = _identity_value(record, keys)
        if marker is None:
            raise MappingFieldMissing(
                "Canonical identity fields must be present and non-blank",
                field=", ".join(str(key) for key in keys),
                record_index=source.get("record_index"),
            )
        markers.append(marker)
    if policy == "allow":
        return mapped, rows, lineage
    output_records: list[dict[str, Any]] = []
    output_rows: list[list[Any]] = []
    output_lineage: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    for record, row, source, marker in zip(mapped, rows, lineage, markers, strict=True):
        if marker not in positions:
            positions[marker] = len(output_records)
            output_records.append(record)
            output_rows.append(row)
            output_lineage.append(source)
            continue
        position = positions[marker]
        if policy == "skip":
            continue
        if policy == "replace":
            output_records[position] = record
            output_rows[position] = row
            output_lineage[position] = source
            continue
        if policy == "merge":
            output_records[position] = _deep_merge(output_records[position], record)
            output_rows[position] = _canonical_row(manifest, output_records[position])
            output_lineage[position] = _combine_lineage(output_lineage[position], source)
            continue
        raise MappingSchemaError(f"Duplicate canonical identity encountered: {marker}")
    return output_records, output_rows, output_lineage


def _deep_merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        elif value is not None:
            merged[key] = deepcopy(value)
    return merged


def _canonical_row(manifest: dict[str, Any], record: dict[str, Any]) -> list[Any]:
    row: list[Any] = []
    for rule in manifest["field_map"]:
        value = _path_get(record, str(rule["target"]))
        row.append(_excel_safe(None if value is _MISSING else value))
    return row


def _combine_lineage(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Keep the latest summary while retaining every source merged into it."""

    def members(value: dict[str, Any]) -> list[dict[str, Any]]:
        nested = value.get("source_records")
        if isinstance(nested, list) and all(isinstance(item, dict) for item in nested):
            return deepcopy(nested)
        return [
            deepcopy(
                {
                    key: item
                    for key, item in value.items()
                    if key not in {"source_records", "source_record_indices", "source_ids"}
                }
            )
        ]

    source_records = [*members(left), *members(right)]
    combined = deepcopy(right)
    combined["source_records"] = source_records
    combined["source_record_indices"] = [
        item.get("record_index") for item in source_records if item.get("record_index") is not None
    ]
    combined["source_ids"] = [
        item.get("source_id") for item in source_records if item.get("source_id") is not None
    ]
    return combined


def _validate_invariants(manifest: dict[str, Any], records: list[dict[str, Any]]) -> None:
    for invariant in manifest.get("invariants") or []:
        if not isinstance(invariant, dict):
            raise MappingSchemaError("Profile invariants must be objects")
        rule = str(invariant.get("rule") or "").strip().lower()
        fields = [str(value) for value in invariant.get("fields") or []]
        if invariant.get("field"):
            fields.append(str(invariant["field"]))
        if rule in {"", "none"}:
            continue
        if rule in {"required_nonempty", "required_non_blank", "required_fields_present"}:
            for index, record in enumerate(records):
                for field in fields:
                    value = _path_get(record, field)
                    if value is _MISSING or _identity_component_is_blank(value):
                        raise MappingFieldMissing(
                            f"Invariant requires canonical field '{field}'",
                            field=field,
                            record_index=index,
                        )
            continue
        if rule == "unique_composite":
            seen: set[str] = set()
            for index, record in enumerate(records):
                marker = _identity_value(record, fields)
                if marker is None:
                    raise MappingFieldMissing(
                        "Unique-composite invariant fields must be present and non-blank",
                        field=", ".join(fields),
                        record_index=index,
                    )
                if marker in seen:
                    raise MappingSchemaError(
                        "Unique-composite invariant encountered a duplicate value",
                        field=", ".join(fields),
                        record_index=index,
                    )
                seen.add(marker)
            continue
        if rule == "nonnegative":
            for index, record in enumerate(records):
                for field in fields:
                    value = _path_get(record, field)
                    if value is _MISSING or value is None:
                        continue
                    try:
                        numeric_value = _number(value)
                    except (InvalidOperation, TypeError, ValueError) as exc:
                        raise MappingTypeError(
                            f"Invariant field '{field}' is not numeric",
                            field=field,
                            record_index=index,
                            expected="number",
                            received=value,
                        ) from exc
                    if numeric_value < 0:
                        raise MappingSchemaError(
                            f"Invariant requires nonnegative canonical field '{field}'",
                            field=field,
                            record_index=index,
                        )
            continue
        if rule == "greater_than":
            threshold = _invariant_number(
                invariant.get("value"),
                field=f"invariants.{invariant.get('id') or rule}.value",
            )
            field = fields[0]
            for index, record in enumerate(records):
                value = _canonical_number(record, field, index)
                if value <= threshold:
                    raise MappingSchemaError(
                        f"Invariant requires canonical field '{field}' to be greater than "
                        f"{threshold}",
                        field=field,
                        record_index=index,
                    )
            continue
        if rule == "mutually_exclusive_nonzero":
            for index, record in enumerate(records):
                values = [
                    _canonical_number(record, field, index)
                    for field in fields
                ]
                if sum(value != 0 for value in values) > 1:
                    raise MappingSchemaError(
                        "Mutually-exclusive fields cannot both be nonzero",
                        field=", ".join(fields),
                        record_index=index,
                    )
            continue
        if rule == "header_equals_line_sum_with_tolerance":
            header_field, line_field = fields
            tolerance = _invariant_tolerance(invariant.get("tolerance", 0))
            for group_records in _records_by_header_identity(manifest, records).values():
                header_values = [
                    _canonical_number(record, header_field, index)
                    for index, record in group_records
                ]
                header_value = header_values[0]
                if any(abs(value - header_value) > tolerance for value in header_values[1:]):
                    raise MappingSchemaError(
                        f"Header field '{header_field}' is inconsistent across flattened lines",
                        field=header_field,
                    )
                line_total = sum(
                    _canonical_number(record, line_field, index)
                    for index, record in group_records
                )
                if abs(header_value - line_total) > tolerance:
                    raise MappingSchemaError(
                        f"Header field '{header_field}' does not reconcile to line field "
                        f"'{line_field}' within tolerance {tolerance}",
                        field=header_field,
                    )
            continue
        if rule == "debits_equal_credits":
            left_field, right_field = fields
            for group_records in _records_by_header_identity(manifest, records).values():
                if "posting" in left_field.casefold() and "type" in left_field.casefold():
                    debit_total: int | float = 0
                    credit_total: int | float = 0
                    for index, record in group_records:
                        posting_type = _path_get(record, left_field)
                        amount = _canonical_number(record, right_field, index)
                        normalized = str(posting_type or "").strip().casefold()
                        if normalized == "debit":
                            debit_total += amount
                        elif normalized == "credit":
                            credit_total += amount
                        else:
                            raise MappingSchemaError(
                                f"Posting type '{posting_type}' is neither debit nor credit",
                                field=left_field,
                                record_index=index,
                            )
                else:
                    debit_total = sum(
                        _canonical_number(record, left_field, index)
                        for index, record in group_records
                    )
                    credit_total = sum(
                        _canonical_number(record, right_field, index)
                        for index, record in group_records
                    )
                if abs(float(debit_total) - float(credit_total)) > 1e-9:
                    raise MappingSchemaError(
                        "Journal debit and credit totals do not reconcile",
                        field=", ".join(fields),
                    )
            continue
        if rule == "sum_equals":
            field = fields[0]
            expected = _invariant_number(
                invariant.get("value"),
                field=f"invariants.{invariant.get('id') or rule}.value",
            )
            for group_records in _records_by_header_identity(manifest, records).values():
                total = sum(
                    _canonical_number(record, field, index)
                    for index, record in group_records
                )
                if abs(float(total) - float(expected)) > 1e-9:
                    raise MappingSchemaError(
                        f"Canonical field '{field}' sums to {total}, expected {expected}",
                        field=field,
                    )
            continue
        if rule == "equals":
            expected = invariant.get("value")
            for index, record in enumerate(records):
                for field in fields:
                    if _path_get(record, field) != expected:
                        raise MappingSchemaError(
                            f"Invariant requires canonical field '{field}' to equal {expected!r}",
                            field=field,
                            record_index=index,
                        )
            continue
        raise MappingSchemaError(
            f"Transformation profile '{manifest['id']}' declares unsupported invariant '{rule}'"
        )


def _invariant_number(value: Any, *, field: str) -> int | float:
    try:
        return _number(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MappingSchemaError(
            "Invariant comparison values must be numeric",
            field=field,
        ) from exc


def _canonical_number(record: dict[str, Any], field: str, index: int) -> int | float:
    value = _path_get(record, field)
    if value is _MISSING or value is None:
        raise MappingFieldMissing(
            f"Invariant requires numeric canonical field '{field}'",
            field=field,
            record_index=index,
        )
    try:
        return _number(value)
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise MappingTypeError(
            f"Invariant field '{field}' is not numeric",
            field=field,
            record_index=index,
            expected="number",
            received=value,
        ) from exc


def _invariant_tolerance(value: Any) -> float:
    if str(value).strip().casefold() == "currency_minor_unit":
        return 0.01
    numeric = _invariant_number(value, field="invariant.tolerance")
    if numeric < 0:
        raise MappingSchemaError(
            "Invariant tolerance cannot be negative",
            field="invariant.tolerance",
        )
    return float(numeric)


def _records_by_header_identity(
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, list[tuple[int, dict[str, Any]]]]:
    """Group flattened lines by canonical identity fields owned by the header."""

    identity = manifest.get("identity") or {}
    source_keys = [str(value) for value in identity.get("source_key") or []]
    canonical_keys = [str(value) for value in identity.get("canonical_key") or []]
    related_paths = [
        str(value) for value in (manifest.get("source") or {}).get("related_objects") or []
    ]
    header_keys = [
        canonical_key
        for source_key, canonical_key in zip(source_keys, canonical_keys, strict=True)
        if not any(
            source_key == related_path or source_key.startswith(f"{related_path}.")
            for related_path in related_paths
        )
    ]
    groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, record in enumerate(records):
        if header_keys:
            marker = _identity_value(record, header_keys)
            if marker is None:
                raise MappingFieldMissing(
                    "Header reconciliation identity fields must be present and non-blank",
                    field=", ".join(header_keys),
                    record_index=index,
                )
        else:
            marker = "__all_records__"
        groups.setdefault(marker, []).append((index, record))
    return groups
