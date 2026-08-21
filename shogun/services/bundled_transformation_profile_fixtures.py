"""Deterministic package-fixture evidence for bundled enterprise profiles.

These fixtures are a release gate for the executable profile contract.  They
do not claim that every tenant has an identical upstream customization; they
prove that the exact packaged source paths, types, transforms, fingerprints,
canonical targets, invariants, table rows, and rejection behavior execute in
the adapter shipped in the same build.

The builder deliberately supports only the bounded ``canonical_entity_map_v1``
vocabulary.  A manifest which declares a future capability remains a governed
candidate and cannot acquire package validation evidence through this module.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from shogun.schemas.transformation_profile import (
    TransformationProfileValidationRequest,
)

BUNDLED_FIXTURE_POLICY = "bundled_canonical_contract_v2"
SUPPORTED_BUNDLED_ADAPTER = "canonical_entity_map_v1"


class BundledTransformationFixtureError(ValueError):
    """The manifest cannot be represented by the bundled fixture policy."""


def build_bundled_validation_request(
    definition: dict[str, Any],
) -> TransformationProfileValidationRequest:
    """Build three exact positive fixtures and two rejection fixtures.

    Values are intentionally deterministic and credential-free.  Expected
    canonical records and spreadsheet-safe rows are calculated independently
    from the runtime adapter so a regression in mapping or coercion fails the
    release/startup gate instead of blessing its own output.
    """

    if str(definition.get("adapter") or "") != SUPPORTED_BUNDLED_ADAPTER:
        raise BundledTransformationFixtureError(
            "Bundled contract fixtures only support canonical_entity_map_v1"
        )
    requirements = definition.get("adapter_requirements") or {}
    if str(requirements.get("status") or "").lower() != "available":
        raise BundledTransformationFixtureError(
            "Only manifests declaring an available adapter may use bundled fixtures"
        )

    field_map = definition.get("field_map")
    if not isinstance(field_map, list) or not field_map:
        raise BundledTransformationFixtureError("Manifest has no field mappings")

    positive_fixtures: list[dict[str, Any]] = []
    for sequence in range(1, 4):
        payload, expected_records, expected_rows = _positive_payload(
            definition, sequence=sequence
        )
        positive_fixtures.append(
            {
                "name": f"packaged contract variant {sequence}",
                "payload": payload,
                "context": {
                    "flow_id": "bundled-profile-validation",
                    "node_id": f"fixture-{sequence}",
                    "source_node_id": "packaged-source",
                },
                "expected_record_count": len(expected_records),
                "expected_contract_id": str(
                    definition["canonical_contract"]["id"]
                ),
                "expected_record_kind": str(
                    definition["canonical_contract"]["record_kind"]
                ),
                "expected_headers": [str(rule["target"]) for rule in field_map],
                "expected_records": expected_records,
                "expected_rows": expected_rows,
            }
        )

    identity_paths = list((definition.get("identity") or {}).get("source_key") or [])
    if not identity_paths:
        identity_paths = [
            str(rule["source"])
            for rule in field_map
            if bool(rule.get("required"))
        ][:1]
    if not identity_paths:
        raise BundledTransformationFixtureError(
            "Manifest needs an identity or required source field for rejection evidence"
        )
    first_positive_payload = deepcopy(positive_fixtures[0]["payload"])
    negative_fixtures = [
        {
            "name": "missing configured record collection",
            "payload": _missing_collection_payload(definition),
            "expected_error_code": "MAPPING_INPUT_ERROR",
        },
        {
            "name": "missing required source identity",
            "payload": _missing_identity_payload(
                definition,
                deepcopy(first_positive_payload),
            ),
            "expected_error_code": "VALIDATION_FAILED",
        },
    ]
    fingerprint_payload = _wrong_positive_fingerprint_payload(
        definition,
        deepcopy(first_positive_payload),
    )
    if fingerprint_payload is not None:
        negative_fixtures.append(
            {
                "name": "wrong positive field fingerprint",
                "payload": fingerprint_payload,
                "expected_error_code": "MAPPING_INPUT_ERROR",
            }
        )
    negative_fixtures.extend(
        _invariant_negative_fixtures(
            definition,
            first_positive_payload,
        )
    )
    definition_hash = hashlib.sha256(
        json.dumps(
            definition,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    return TransformationProfileValidationRequest.model_validate(
        {
            "positive_fixtures": positive_fixtures,
            "negative_fixtures": negative_fixtures,
            "report": {
                "policy": BUNDLED_FIXTURE_POLICY,
                "profile_content_hash": definition_hash,
                "evidence_scope": (
                    "packaged source paths, field types, transforms, fingerprints, "
                    "canonical targets, invariant-specific rejection, rows, and "
                    "structural rejection behavior"
                ),
                "tenant_payload_certified": False,
            },
            "actor": "bundled_profile_validation",
        }
    )


def _missing_identity_payload(
    definition: dict[str, Any],
    payload: Any,
) -> Any:
    """Blank a real source identity in an otherwise valid packaged payload."""

    for source_path in (definition.get("identity") or {}).get("source_key") or []:
        mapping = next(
            (
                rule
                for rule in definition.get("field_map") or []
                if str(rule.get("source") or "") == str(source_path)
            ),
            None,
        )
        if not isinstance(mapping, dict) or str(mapping.get("type") or "").lower() != "string":
            continue
        location = _fixture_source_location(
            definition,
            payload,
            str(source_path),
            record_index=0,
        )
        if location is not None:
            container, local_path = location
            # A blank value still satisfies the structural field fingerprint,
            # so this fixture reaches and proves the identity-completeness gate.
            _path_set(container, local_path, " ")
            return payload
    raise BundledTransformationFixtureError(
        "Could not locate a packaged source identity for negative evidence"
    )


def _wrong_positive_fingerprint_payload(
    definition: dict[str, Any],
    payload: Any,
) -> Any | None:
    """Break one declared data fingerprint while preserving the payload wrapper."""

    fingerprints = (definition.get("selection") or {}).get("positive_fingerprints") or []
    for raw_fingerprint in fingerprints:
        parsed = _field_fingerprint(str(raw_fingerprint))
        if parsed is None:
            continue
        source_path, expected = parsed
        location = _fixture_source_location(
            definition,
            payload,
            source_path,
            record_index=0,
        )
        if location is None:
            continue
        container, local_path = location
        if expected is None:
            if _path_delete(container, local_path):
                return payload
            continue
        _path_set(container, local_path, f"not-{expected}")
        return payload
    return None


def _invariant_negative_fixtures(
    definition: dict[str, Any],
    positive_payload: Any,
) -> list[dict[str, Any]]:
    """Build an independent rejecting payload for every non-identity invariant."""

    fixtures: list[dict[str, Any]] = []
    identity_fields = set(
        str(value) for value in (definition.get("identity") or {}).get("canonical_key") or []
    )
    for invariant in definition.get("invariants") or []:
        invariant_id = str(invariant.get("id") or invariant.get("rule") or "invariant")
        rule = str(invariant.get("rule") or "").strip().lower()
        fields = [
            str(value)
            for value in [*(invariant.get("fields") or []), invariant.get("field")]
            if value
        ]
        if rule in {"", "none"}:
            continue
        if rule in {"required_nonempty", "required_non_blank"} and set(fields) <= identity_fields:
            # The dedicated missing-identity fixture already proves this exact rule.
            continue

        payload = deepcopy(positive_payload)
        if rule in {"required_nonempty", "required_non_blank", "required_fields_present"}:
            candidates = [field for field in fields if field not in identity_fields] or fields
            deleted = any(
                _delete_fixture_target_value(
                    definition,
                    payload,
                    target,
                    record_index=0,
                )
                for target in candidates
            )
            if not deleted:
                raise BundledTransformationFixtureError(
                    f"Could not remove a mapped source for invariant '{invariant_id}'"
                )
            expected_error_code = "VALIDATION_FAILED"
        elif rule == "unique_composite":
            _duplicate_first_fixture_record(definition, payload)
            expected_error_code = "MAPPING_SCHEMA_ERROR"
        elif rule == "nonnegative":
            _set_fixture_target_value(definition, payload, fields[0], -1)
            expected_error_code = "MAPPING_SCHEMA_ERROR"
        elif rule == "greater_than":
            _set_fixture_target_value(
                definition,
                payload,
                fields[0],
                invariant.get("value"),
            )
            expected_error_code = "MAPPING_SCHEMA_ERROR"
        elif rule == "mutually_exclusive_nonzero":
            for target in fields:
                _set_fixture_target_value(definition, payload, target, 125)
            expected_error_code = "MAPPING_SCHEMA_ERROR"
        elif rule == "header_equals_line_sum_with_tolerance":
            _set_fixture_target_value(definition, payload, fields[0], 999_999)
            expected_error_code = "MAPPING_SCHEMA_ERROR"
        elif rule == "debits_equal_credits":
            # Positive fixtures balance at 125 per side. Perturb one numeric
            # operand while preserving every identity and posting-type field.
            _set_fixture_target_value(
                definition,
                payload,
                fields[-1],
                126,
                record_index=0,
            )
            expected_error_code = "MAPPING_SCHEMA_ERROR"
        elif rule == "sum_equals":
            _set_fixture_target_value(
                definition,
                payload,
                fields[0],
                999,
                record_index=0,
            )
            expected_error_code = "MAPPING_SCHEMA_ERROR"
        elif rule == "equals":
            _set_fixture_target_value(
                definition,
                payload,
                fields[0],
                "__INVALID__",
            )
            expected_error_code = "MAPPING_SCHEMA_ERROR"
        else:
            raise BundledTransformationFixtureError(
                f"Bundled negative fixture policy does not implement invariant '{rule}'"
            )
        fixtures.append(
            {
                "name": f"rejects invariant {invariant_id}",
                "payload": payload,
                "expected_error_code": expected_error_code,
            }
        )
    return fixtures


def _positive_payload(
    definition: dict[str, Any],
    *,
    sequence: int,
) -> tuple[Any, list[dict[str, Any]], list[list[Any]]]:
    capabilities = set(
        (definition.get("adapter_requirements") or {}).get("capabilities") or []
    )
    if "heterogeneous_object_union" in capabilities:
        return _positive_union_payload(definition, sequence=sequence)
    if "nested_collection_flattening" in capabilities:
        return _positive_header_line_payload(definition, sequence=sequence)
    source_record, expected_record, expected_row = _positive_record(
        definition,
        sequence=sequence,
    )
    return _wrap_record(definition, source_record), [expected_record], [expected_row]


def _positive_header_line_payload(
    definition: dict[str, Any],
    *,
    sequence: int,
) -> tuple[Any, list[dict[str, Any]], list[list[Any]]]:
    source = definition.get("source") or {}
    related_objects = [str(value) for value in source.get("related_objects") or []]
    if len(related_objects) != 1:
        raise BundledTransformationFixtureError(
            "Nested collection fixtures require exactly one related object path"
        )
    related_path = related_objects[0]
    line_target_path = _line_target_path(definition, related_path)
    logical_sources: list[dict[str, Any]] = []
    expected_records: list[dict[str, Any]] = []
    expected_rows: list[list[Any]] = []
    for line_index in range(2):
        logical, expected, row = _positive_record(
            definition,
            sequence=sequence * 10 + line_index,
        )
        logical_sources.append(logical)
        expected_records.append(expected)
        expected_rows.append(row)

    # A header is shared by all expanded lines. Make every non-line value
    # identical while retaining distinct line identities and amounts.
    for rule_index, rule in enumerate(definition["field_map"]):
        source_path = str(rule["source"])
        if source_path.startswith(f"{line_target_path}."):
            continue
        raw = _path_get(logical_sources[0], source_path)
        expected = _path_get(expected_records[0], str(rule["target"]))
        if raw is not _MISSING:
            _path_set(logical_sources[1], source_path, raw)
        if expected is not _MISSING:
            _path_set(expected_records[1], str(rule["target"]), expected)
            expected_rows[1][rule_index] = _spreadsheet_safe(expected)

    _balance_group_invariants(
        definition,
        logical_sources,
        expected_records,
        expected_rows,
    )

    raw_header = deepcopy(logical_sources[0])
    lines: list[dict[str, Any]] = []
    for logical in logical_sources:
        line = _path_get(logical, line_target_path)
        if not isinstance(line, dict):
            raise BundledTransformationFixtureError(
                f"Fixture line path '{line_target_path}' did not resolve to an object"
            )
        lines.append(deepcopy(line))
    if "synthetic_line_index" in set(
        (definition.get("adapter_requirements") or {}).get("capabilities") or []
    ):
        for line in lines:
            line.pop("_index", None)
        line_id_target = str((definition.get("identity") or {}).get("canonical_key", [""])[-1])
        for line_index, expected in enumerate(expected_records):
            _replace_expected_target(
                definition,
                expected,
                expected_rows[line_index],
                line_id_target,
                line_index,
            )
    _path_set(raw_header, line_target_path, lines)
    return _wrap_record(definition, raw_header), expected_records, expected_rows


def _positive_union_payload(
    definition: dict[str, Any],
    *,
    sequence: int,
) -> tuple[Any, list[dict[str, Any]], list[list[Any]]]:
    source = definition.get("source") or {}
    union_paths = [str(value) for value in source.get("union_paths") or []]
    discriminator = str(source.get("union_discriminator") or "").strip()
    if len(union_paths) < 2 or not discriminator:
        raise BundledTransformationFixtureError(
            "Heterogeneous union fixtures require paths and a discriminator"
        )
    payload: dict[str, Any] = {}
    expected_records: list[dict[str, Any]] = []
    expected_rows: list[list[Any]] = []
    discriminator_rule = next(
        (
            rule
            for rule in definition["field_map"]
            if str(rule["source"]) == discriminator
        ),
        None,
    )
    if discriminator_rule is None:
        raise BundledTransformationFixtureError(
            "Union discriminator must be mapped into the canonical contract"
        )
    for union_index, union_path in enumerate(union_paths):
        logical, expected, row = _positive_record(
            definition,
            sequence=sequence * 10 + union_index,
        )
        discriminator_value = union_path.rsplit(".", 1)[-1]
        _path_delete(logical, discriminator)
        mapped_discriminator = _expected_value(discriminator_rule, discriminator_value)
        _path_set(expected, str(discriminator_rule["target"]), mapped_discriminator)
        rule_index = definition["field_map"].index(discriminator_rule)
        row[rule_index] = _spreadsheet_safe(mapped_discriminator)
        _path_set(payload, union_path, [logical])
        expected_records.append(expected)
        expected_rows.append(row)
    return payload, expected_records, expected_rows


def _line_target_path(definition: dict[str, Any], related_path: str) -> str:
    """Mirror the adapter's explicit related-object wrapper selection."""

    declared_paths = [
        str(rule.get("source") or "") for rule in definition.get("field_map") or []
    ]
    for wrapper in ("items", "value", "records", "collection", "result"):
        wrapped = f"{related_path}.{wrapper}"
        if any(path.startswith(f"{wrapped}.") for path in declared_paths):
            return wrapped
    return related_path


def _balance_group_invariants(
    definition: dict[str, Any],
    logical_sources: list[dict[str, Any]],
    expected_records: list[dict[str, Any]],
    expected_rows: list[list[Any]],
) -> None:
    """Make multi-line fixtures satisfy each declared financial invariant."""

    for invariant in definition.get("invariants") or []:
        rule = str(invariant.get("rule") or "").lower()
        fields = [
            str(value)
            for value in [*(invariant.get("fields") or []), invariant.get("field")]
            if value
        ]
        if rule == "header_equals_line_sum_with_tolerance":
            header_field, line_field = fields
            line_values = [100 + index for index in range(len(logical_sources))]
            for index, value in enumerate(line_values):
                _replace_mapped_value(
                    definition,
                    logical_sources[index],
                    expected_records[index],
                    expected_rows[index],
                    line_field,
                    value,
                )
            header_total = sum(line_values)
            for index in range(len(logical_sources)):
                _replace_mapped_value(
                    definition,
                    logical_sources[index],
                    expected_records[index],
                    expected_rows[index],
                    header_field,
                    header_total,
                )
        elif rule == "mutually_exclusive_nonzero":
            left, right = fields
            values = [(125, 0), (0, 125)]
            for index, (left_value, right_value) in enumerate(values):
                _replace_mapped_value(
                    definition,
                    logical_sources[index],
                    expected_records[index],
                    expected_rows[index],
                    left,
                    left_value,
                )
                _replace_mapped_value(
                    definition,
                    logical_sources[index],
                    expected_records[index],
                    expected_rows[index],
                    right,
                    right_value,
                )
        elif rule == "debits_equal_credits":
            left, right = fields
            left_rule = _mapping_for_target(definition, left)
            if str(left_rule.get("type") or "").lower() == "string":
                for index, posting_type in enumerate(("Debit", "Credit")):
                    _replace_mapped_value(
                        definition,
                        logical_sources[index],
                        expected_records[index],
                        expected_rows[index],
                        left,
                        posting_type,
                    )
                    _replace_mapped_value(
                        definition,
                        logical_sources[index],
                        expected_records[index],
                        expected_rows[index],
                        right,
                        125,
                    )
            else:
                for index, (debit, credit) in enumerate(((125, 0), (0, 125))):
                    _replace_mapped_value(
                        definition,
                        logical_sources[index],
                        expected_records[index],
                        expected_rows[index],
                        left,
                        debit,
                    )
                    _replace_mapped_value(
                        definition,
                        logical_sources[index],
                        expected_records[index],
                        expected_rows[index],
                        right,
                        credit,
                    )
        elif rule == "sum_equals":
            target = fields[0]
            total = invariant.get("value", 0)
            first = 125
            values = [first, total - first]
            for index, value in enumerate(values):
                _replace_mapped_value(
                    definition,
                    logical_sources[index],
                    expected_records[index],
                    expected_rows[index],
                    target,
                    value,
                )


def _mapping_for_target(
    definition: dict[str, Any], target_path: str
) -> dict[str, Any]:
    mapping = next(
        (
            rule
            for rule in definition.get("field_map") or []
            if str(rule.get("target") or "") == target_path
        ),
        None,
    )
    if not isinstance(mapping, dict):
        raise BundledTransformationFixtureError(
            f"Invariant target '{target_path}' has no field mapping"
        )
    return mapping


def _replace_mapped_value(
    definition: dict[str, Any],
    logical_source: dict[str, Any],
    expected_record: dict[str, Any],
    expected_row: list[Any],
    target_path: str,
    value: Any,
) -> None:
    mapping = _mapping_for_target(definition, target_path)
    raw = _raw_value_for_rule(mapping, value)
    mapped = _expected_value(mapping, raw)
    _path_set(logical_source, str(mapping["source"]), raw)
    _replace_expected_target(
        definition,
        expected_record,
        expected_row,
        target_path,
        mapped,
    )


def _replace_expected_target(
    definition: dict[str, Any],
    expected_record: dict[str, Any],
    expected_row: list[Any],
    target_path: str,
    value: Any,
) -> None:
    mapping = _mapping_for_target(definition, target_path)
    _path_set(expected_record, target_path, value)
    expected_row[definition["field_map"].index(mapping)] = _spreadsheet_safe(value)


def _positive_record(
    definition: dict[str, Any],
    *,
    sequence: int,
) -> tuple[dict[str, Any], dict[str, Any], list[Any]]:
    source_record: dict[str, Any] = {}
    expected_record: dict[str, Any] = {}
    expected_row: list[Any] = []
    equals_targets = {
        str(field): invariant.get("value")
        for invariant in definition.get("invariants") or []
        if str(invariant.get("rule") or "").lower() == "equals"
        for field in [*(invariant.get("fields") or []), invariant.get("field")]
        if field
    }

    for index, rule in enumerate(definition["field_map"]):
        source_path = str(rule["source"])
        target_path = str(rule["target"])
        expected = (
            deepcopy(equals_targets[target_path])
            if target_path in equals_targets
            else _value_for_rule(rule, sequence=sequence, index=index)
        )
        raw = _raw_value_for_rule(rule, expected)
        _path_set(source_record, source_path, raw)
        _path_set(expected_record, target_path, expected)
        expected_row.append(_spreadsheet_safe(expected))

    # Fingerprints may reference discriminator fields which are intentionally
    # not copied into the canonical contract.
    for raw_fingerprint in (definition.get("selection") or {}).get(
        "positive_fingerprints", []
    ):
        parsed = _field_fingerprint(str(raw_fingerprint))
        if parsed is None:
            continue
        path, expected = parsed
        if _path_get(source_record, path) is _MISSING:
            _path_set(
                source_record,
                path,
                expected if expected is not None else f"fingerprint-{sequence}",
            )
        elif expected is not None:
            _path_set(source_record, path, expected)
            for rule in definition["field_map"]:
                if str(rule["source"]) != path:
                    continue
                target_path = str(rule["target"])
                mapped = _expected_value(rule, expected)
                _path_set(expected_record, target_path, mapped)
                expected_row[definition["field_map"].index(rule)] = _spreadsheet_safe(
                    mapped
                )

    return source_record, expected_record, expected_row


def _value_for_rule(rule: dict[str, Any], *, sequence: int, index: int) -> Any:
    field_type = str(rule.get("type") or "any").lower()
    if field_type in {"integer"}:
        return sequence * 10 + index
    if field_type in {"number", "decimal"}:
        return sequence * 100 + index + 0.25
    if field_type == "boolean":
        return sequence % 2 == 1
    if field_type == "date":
        day = ((sequence - 1) % 28) + 1
        return f"2026-08-{day:02d}"
    if field_type == "datetime":
        day = ((sequence - 1) % 28) + 1
        hour = sequence % 24
        return f"2026-08-{day:02d}T{hour:02d}:00:00"
    if field_type == "array":
        return [f"fixture-{sequence}-{index}"]
    if field_type == "object":
        return {"fixture": f"{sequence}-{index}"}
    value = f"fixture-{sequence}-{index}"
    transforms = [
        str(item if isinstance(item, str) else item.get("name") or item.get("type") or "")
        .strip()
        .lower()
        for item in rule.get("transforms") or []
    ]
    if "uppercase" in transforms:
        return value.upper()
    if "lowercase" in transforms:
        return value.lower()
    return value


def _raw_value_for_rule(rule: dict[str, Any], expected: Any) -> Any:
    raw = deepcopy(expected)
    transforms = [
        str(item if isinstance(item, str) else item.get("name") or item.get("type") or "")
        .strip()
        .lower()
        for item in rule.get("transforms") or []
    ]
    if isinstance(raw, str):
        if "uppercase" in transforms:
            raw = raw.lower()
        elif "lowercase" in transforms:
            raw = raw.upper()
        if "trim" in transforms:
            raw = f"  {raw}  "
    return raw


def _expected_value(rule: dict[str, Any], raw: Any) -> Any:
    value = deepcopy(raw)
    for transform in rule.get("transforms") or []:
        name = str(
            transform
            if isinstance(transform, str)
            else transform.get("name") or transform.get("type") or ""
        ).lower()
        if name == "trim" and isinstance(value, str):
            value = value.strip()
        elif name == "uppercase":
            value = str(value).upper()
        elif name == "lowercase":
            value = str(value).lower()
        elif name not in {"", "none"}:
            raise BundledTransformationFixtureError(
                f"Bundled fixture policy does not implement transform '{name}'"
            )
    return value


def _wrap_record(definition: dict[str, Any], record: dict[str, Any]) -> Any:
    source = definition.get("source") or {}
    record_path = str(source.get("record_path") or "").strip()
    record_shape = str(source.get("record_shape") or "").strip().lower()
    records: Any = record if record_shape in {"entity", "object", "single"} else [record]
    if not record_path:
        return records
    payload: dict[str, Any] = {}
    _path_set(payload, record_path, records)
    return payload


def _missing_collection_payload(definition: dict[str, Any]) -> Any:
    record_path = str((definition.get("source") or {}).get("record_path") or "").strip()
    return {} if record_path else []


def _fixture_record_views(
    definition: dict[str, Any],
    payload: Any,
) -> list[tuple[dict[str, Any], dict[str, Any] | None]]:
    """Return physical header/line views from a builder-owned fixture payload."""

    source = definition.get("source") or {}
    capabilities = set(
        (definition.get("adapter_requirements") or {}).get("capabilities") or []
    )
    if "heterogeneous_object_union" in capabilities:
        views: list[tuple[dict[str, Any], dict[str, Any] | None]] = []
        for union_path in source.get("union_paths") or []:
            selected = _path_get(payload, str(union_path))
            if selected is _MISSING:
                continue
            records = selected if isinstance(selected, list) else [selected]
            if any(not isinstance(record, dict) for record in records):
                raise BundledTransformationFixtureError(
                    f"Union fixture path '{union_path}' is not an object collection"
                )
            views.extend((record, None) for record in records)
        return views

    record_path = str(source.get("record_path") or "").strip()
    selected = _path_get(payload, record_path) if record_path else payload
    records = selected if isinstance(selected, list) else [selected]
    if any(not isinstance(record, dict) for record in records):
        raise BundledTransformationFixtureError(
            f"Fixture record path '{record_path or '<root>'}' is not an object collection"
        )
    if "nested_collection_flattening" not in capabilities:
        return [(record, None) for record in records]

    related_objects = [str(value) for value in source.get("related_objects") or []]
    if len(related_objects) != 1:
        raise BundledTransformationFixtureError(
            "Nested fixture mutation requires exactly one related object path"
        )
    line_path = _line_target_path(definition, related_objects[0])
    views = []
    for header in records:
        selected_lines = _path_get(header, line_path)
        lines = selected_lines if isinstance(selected_lines, list) else [selected_lines]
        if any(not isinstance(line, dict) for line in lines):
            raise BundledTransformationFixtureError(
                f"Fixture line path '{line_path}' is not an object collection"
            )
        views.extend((header, line) for line in lines)
    return views


def _fixture_source_location(
    definition: dict[str, Any],
    payload: Any,
    source_path: str,
    *,
    record_index: int,
) -> tuple[dict[str, Any], str] | None:
    views = _fixture_record_views(definition, payload)
    if record_index >= len(views):
        raise BundledTransformationFixtureError(
            f"Fixture has no source record at index {record_index}"
        )
    header, line = views[record_index]
    related_objects = [
        str(value) for value in (definition.get("source") or {}).get("related_objects") or []
    ]
    if line is not None and related_objects:
        line_path = _line_target_path(definition, related_objects[0])
        prefix = f"{line_path}."
        if source_path.startswith(prefix):
            return line, source_path[len(prefix) :]
    if _path_get(header, source_path) is not _MISSING:
        return header, source_path
    return None


def _set_fixture_target_value(
    definition: dict[str, Any],
    payload: Any,
    target_path: str,
    value: Any,
    *,
    record_index: int = 0,
) -> None:
    mapping = _mapping_for_target(definition, target_path)
    source_path = str(mapping["source"])
    location = _fixture_source_location(
        definition,
        payload,
        source_path,
        record_index=record_index,
    )
    if location is None:
        raise BundledTransformationFixtureError(
            f"Could not locate source '{source_path}' for target '{target_path}'"
        )
    container, local_path = location
    _path_set(container, local_path, _raw_value_for_rule(mapping, value))


def _delete_fixture_target_value(
    definition: dict[str, Any],
    payload: Any,
    target_path: str,
    *,
    record_index: int,
) -> bool:
    mapping = _mapping_for_target(definition, target_path)
    return _delete_fixture_source_value(
        definition,
        payload,
        str(mapping["source"]),
        record_index=record_index,
    )


def _delete_fixture_source_value(
    definition: dict[str, Any],
    payload: Any,
    source_path: str,
    *,
    record_index: int,
) -> bool:
    location = _fixture_source_location(
        definition,
        payload,
        source_path,
        record_index=record_index,
    )
    if location is None:
        return False
    container, local_path = location
    return _path_delete(container, local_path)


def _duplicate_first_fixture_record(definition: dict[str, Any], payload: Any) -> None:
    """Duplicate one physical record so canonical identity enforcement rejects it."""

    source = definition.get("source") or {}
    capabilities = set(
        (definition.get("adapter_requirements") or {}).get("capabilities") or []
    )
    if "heterogeneous_object_union" in capabilities:
        first_path = str((source.get("union_paths") or [""])[0])
        records = _path_get(payload, first_path)
    else:
        record_path = str(source.get("record_path") or "").strip()
        records = _path_get(payload, record_path) if record_path else payload
    if not isinstance(records, list) or not records or not isinstance(records[0], dict):
        raise BundledTransformationFixtureError(
            "Uniqueness fixture requires a physical source-record collection"
        )
    if "nested_collection_flattening" in capabilities:
        related_objects = [str(value) for value in source.get("related_objects") or []]
        line_path = _line_target_path(definition, related_objects[0])
        lines = _path_get(records[0], line_path)
        if not isinstance(lines, list) or not lines or not isinstance(lines[0], dict):
            raise BundledTransformationFixtureError(
                "Uniqueness fixture requires a physical line collection"
            )
        lines.append(deepcopy(lines[0]))
    else:
        records.append(deepcopy(records[0]))


def _field_fingerprint(value: str) -> tuple[str, str | None] | None:
    value = value.strip()
    if value.startswith(("object:", "transport:")):
        return None
    expression = value.split(":", 1)[1] if value.startswith(("field:", "path:")) else value
    path, separator, expected = expression.partition("=")
    return path.strip(), expected.strip() if separator else None


def _spreadsheet_safe(value: Any) -> Any:
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


_MISSING = object()


def _path_get(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return _MISSING
    return current


def _path_set(target: dict[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    current = target
    for part in parts[:-1]:
        nested = current.get(part)
        if not isinstance(nested, dict):
            nested = {}
            current[part] = nested
        current = nested
    current[parts[-1]] = deepcopy(value)


def _path_delete(target: dict[str, Any], path: str) -> bool:
    parts = path.split(".")
    current: Any = target
    for part in parts[:-1]:
        if not isinstance(current, dict):
            return False
        current = current.get(part)
    if isinstance(current, dict):
        sentinel = object()
        return current.pop(parts[-1], sentinel) is not sentinel
    return False
