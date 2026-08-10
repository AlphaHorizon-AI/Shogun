"""Profile-driven deterministic transformations for AgentFlow.

The runtime contains only generic parsing and matrix-building primitives.  All
source labels, record types, field meanings, and destination rules must be
declared by an explicit Mapping/RPA transformation profile.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

SUPPORTED_ADAPTER = "sectioned_record_matrix_v1"


@dataclass(slots=True)
class DeterministicMatrixResult:
    adapter_id: str
    profile_id: str
    rows: list[list[Any]]


@dataclass(slots=True)
class _RecordSection:
    key: str
    fields: dict[str, Any] = field(default_factory=dict)
    records: list[dict[str, str]] = field(default_factory=list)


_MONTH_NAMES = {
    "jan": 1,
    "january": 1,
    "januar": 1,
    "feb": 2,
    "february": 2,
    "februar": 2,
    "mar": 3,
    "march": 3,
    "marz": 3,
    "märz": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "mai": 5,
    "jun": 6,
    "june": 6,
    "juni": 6,
    "jul": 7,
    "july": 7,
    "juli": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "okt": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
    "dez": 12,
    "dezember": 12,
}


def try_deterministic_matrix_transform(
    *,
    profile: dict[str, Any],
    source_context: str,
    fixed_context: str,
) -> DeterministicMatrixResult:
    """Execute the explicitly selected transformation profile.

    A profile is never discovered from task wording or source contents.  The
    caller must supply the profile attached to the upstream Mapping/RPA node.
    """

    profile_id, parameters = _profile_parameters(profile)
    _validate_required_source_patterns(source_context, parameters, profile_id)
    headers, logical_width = _excel_template_contract(fixed_context, parameters, profile_id)
    sections = _parse_sections(source_context, parameters, profile_id)
    planning_columns = _planning_month_columns(headers, parameters)
    rows = _build_rows(
        sections,
        logical_width,
        planning_columns,
        parameters,
        profile_id,
    )
    if not rows:
        raise ValueError(f"Transformation profile '{profile_id}' produced no rows.")
    if any(len(row) != logical_width for row in rows):
        raise ValueError(
            f"Transformation profile '{profile_id}' produced a row outside the "
            f"{logical_width}-column template contract."
        )
    return DeterministicMatrixResult(
        adapter_id=SUPPORTED_ADAPTER,
        profile_id=profile_id,
        rows=rows,
    )


def deterministic_profile_source_units(
    profile: dict[str, Any],
    source_context: str,
) -> list[str]:
    """Split source text at the explicit profile's section boundaries."""

    _profile_id, parameters = _profile_parameters(profile)
    pattern = _required_pattern(parameters, "section_pattern")
    matches = list(pattern.finditer(str(source_context or "")))
    if not matches:
        return [source_context] if source_context else []
    units: list[str] = []
    for index, match in enumerate(matches):
        start = 0 if index == 0 else match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source_context)
        units.append(source_context[start:end])
    return units


def expected_deterministic_matrix_rows(
    profile: dict[str, Any],
    source_context: str,
) -> int:
    """Count rows required by a profile without relying on domain heuristics."""

    profile_id, parameters = _profile_parameters(profile)
    sections = _parse_sections(source_context, parameters, profile_id)
    total = 0
    for section in sections:
        for rule in _row_rules(parameters):
            kind = str(rule.get("kind") or "").strip().lower()
            if kind == "section":
                total += int(_section_condition_matches(section, rule.get("when")))
            elif kind == "record":
                total += sum(1 for record in section.records if _record_matches(record, rule.get("match")))
            elif kind == "aggregate":
                total += int(any(_record_matches(record, rule.get("match")) for record in section.records))
            else:
                raise ValueError(
                    f"Transformation profile '{profile_id}' has unsupported row rule kind '{kind}'."
                )
    return total


def _profile_parameters(profile: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(profile, dict):
        raise ValueError("Transformation profile must be an object.")
    profile_id = str(profile.get("id") or "").strip()
    if not profile_id:
        raise ValueError("Transformation profile requires an id.")
    adapter = str(profile.get("adapter") or "").strip()
    if adapter != SUPPORTED_ADAPTER:
        raise ValueError(
            f"Transformation profile '{profile_id}' uses unsupported adapter '{adapter}'."
        )
    parameters = profile.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError(f"Transformation profile '{profile_id}' requires parameters.")
    return profile_id, parameters


def _validate_required_source_patterns(
    source_context: str,
    parameters: dict[str, Any],
    profile_id: str,
) -> None:
    for raw_pattern in parameters.get("required_source_patterns") or []:
        if not re.search(str(raw_pattern), source_context or ""):
            raise ValueError(
                f"Runtime source does not match transformation profile '{profile_id}'."
            )


def _parse_sections(
    source_context: str,
    parameters: dict[str, Any],
    profile_id: str,
) -> list[_RecordSection]:
    text = str(source_context or "")
    section_pattern = _required_pattern(parameters, "section_pattern")
    key_group = str(parameters.get("section_key_group") or "section_id")
    matches = list(section_pattern.finditer(text))
    if not matches:
        raise ValueError(f"Transformation profile '{profile_id}' found no source sections.")

    record_pattern = _required_pattern(parameters, "record_pattern")
    record_section_key_group = str(parameters.get("record_section_key_group") or "").strip()
    sections: dict[str, _RecordSection] = {}
    for index, match in enumerate(matches):
        try:
            key = str(match.group(key_group)).strip()
        except (IndexError, KeyError) as exc:
            raise ValueError(
                f"Transformation profile '{profile_id}' section pattern lacks group '{key_group}'."
            ) from exc
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section_text = text[match.start():end]
        section = sections.setdefault(key, _RecordSection(key=key))
        _extract_section_fields(section, section_text, parameters, profile_id)
        _extract_selector_fields(section, section_text, parameters, profile_id)
        for record_match in record_pattern.finditer(section_text):
            record = {
                name: str(value or "").strip()
                for name, value in record_match.groupdict().items()
            }
            if record_section_key_group and record.get(record_section_key_group) != key:
                continue
            section.records.append(record)
    return list(sections.values())


def _extract_section_fields(
    section: _RecordSection,
    section_text: str,
    parameters: dict[str, Any],
    profile_id: str,
) -> None:
    for rule in parameters.get("section_fields") or []:
        if not isinstance(rule, dict):
            raise ValueError(f"Transformation profile '{profile_id}' has an invalid section field rule.")
        target = str(rule.get("target") or "").strip()
        pattern = _compile_pattern(rule.get("pattern"), f"section field '{target}'")
        group = str(rule.get("group") or "value")
        values: list[Any] = []
        for match in pattern.finditer(section_text):
            try:
                values.append(_convert_value(match.group(group), rule.get("value_type")))
            except (IndexError, KeyError) as exc:
                raise ValueError(
                    f"Transformation profile '{profile_id}' section field '{target}' "
                    f"lacks group '{group}'."
                ) from exc
        if values:
            _store_aggregated_field(section.fields, target, values, str(rule.get("aggregate") or "first"))


def _extract_selector_fields(
    section: _RecordSection,
    section_text: str,
    parameters: dict[str, Any],
    profile_id: str,
) -> None:
    for rule in parameters.get("selector_fields") or []:
        if not isinstance(rule, dict):
            raise ValueError(f"Transformation profile '{profile_id}' has an invalid selector rule.")
        target = str(rule.get("target") or "").strip()
        scope_pattern = _compile_pattern(rule.get("scope_pattern"), f"selector scope '{target}'")
        line_pattern = _compile_pattern(rule.get("line_pattern"), f"selector line '{target}'")
        scope_group = str(rule.get("scope_group") or "body")
        value_group = str(rule.get("value_group") or "value")
        text_group = str(rule.get("text_group") or "text")
        include_terms = [str(value).casefold() for value in rule.get("include_terms") or []]
        exclude_terms = [str(value).casefold() for value in rule.get("exclude_terms") or []]
        values: list[Any] = []
        for scope_match in scope_pattern.finditer(section_text):
            try:
                body = scope_match.group(scope_group)
            except (IndexError, KeyError) as exc:
                raise ValueError(
                    f"Transformation profile '{profile_id}' selector '{target}' lacks "
                    f"scope group '{scope_group}'."
                ) from exc
            for line_match in line_pattern.finditer(body):
                try:
                    classifier = str(line_match.group(text_group) or "").casefold()
                    value = line_match.group(value_group)
                except (IndexError, KeyError) as exc:
                    raise ValueError(
                        f"Transformation profile '{profile_id}' selector '{target}' has invalid groups."
                    ) from exc
                if include_terms and not any(term in classifier for term in include_terms):
                    continue
                if any(term in classifier for term in exclude_terms):
                    continue
                values.append(_convert_value(value, rule.get("value_type")))
        if values:
            _store_aggregated_field(section.fields, target, values, str(rule.get("aggregate") or "first"))


def _store_aggregated_field(
    fields: dict[str, Any],
    target: str,
    values: list[Any],
    aggregate: str,
) -> None:
    if aggregate == "max":
        value = max(values)
        if target in fields:
            value = max(fields[target], value)
        fields[target] = value
    elif aggregate == "last":
        fields[target] = values[-1]
    elif aggregate == "first":
        if target not in fields or fields[target] in (None, ""):
            fields[target] = values[0]
    else:
        raise ValueError(f"Unsupported field aggregate '{aggregate}'.")


def _excel_template_contract(
    fixed_context: str,
    parameters: dict[str, Any],
    profile_id: str,
) -> tuple[list[Any], int]:
    marker = "[MACHINE-READABLE TEMPLATE MANIFEST]"
    marker_index = str(fixed_context or "").find(marker)
    if marker_index < 0:
        raise ValueError(f"Transformation profile '{profile_id}' requires an Excel template manifest.")
    json_start = fixed_context.find("{", marker_index + len(marker))
    if json_start < 0:
        raise ValueError(f"Transformation profile '{profile_id}' found an invalid template manifest.")
    try:
        manifest, _ = json.JSONDecoder().raw_decode(fixed_context[json_start:])
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Transformation profile '{profile_id}' found an invalid template manifest.") from exc
    if not isinstance(manifest, dict) or manifest.get("kind") != "excel":
        raise ValueError(f"Transformation profile '{profile_id}' requires an Excel template.")
    sheets = manifest.get("sheets") or []
    if not sheets or not isinstance(sheets[0], dict):
        raise ValueError(f"Transformation profile '{profile_id}' requires an Excel sheet contract.")
    sheet = sheets[0]
    preview_rows = sheet.get("preview_rows") or []
    headers = list(preview_rows[0]) if preview_rows and isinstance(preview_rows[0], list) else []
    try:
        logical_width = int(sheet.get("logical_columns") or len(headers))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Transformation profile '{profile_id}' has an invalid column count.") from exc
    template = parameters.get("template") or {}
    minimum_columns = int(template.get("minimum_columns") or 1)
    if logical_width < minimum_columns or len(headers) < logical_width:
        raise ValueError(
            f"Transformation profile '{profile_id}' requires at least {minimum_columns} template columns."
        )
    for raw_index, accepted in (template.get("expected_headers") or {}).items():
        index = int(raw_index)
        aliases = accepted if isinstance(accepted, list) else [accepted]
        if index >= logical_width or _canonical_header(headers[index]) not in {
            _canonical_header(alias) for alias in aliases
        }:
            raise ValueError(
                f"Transformation profile '{profile_id}' does not match template column {index + 1}."
            )
    return headers[:logical_width], logical_width


def _build_rows(
    sections: list[_RecordSection],
    logical_width: int,
    planning_columns: dict[str, int],
    parameters: dict[str, Any],
    profile_id: str,
) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for section in sections:
        base = [""] * logical_width
        for raw_column, value_spec in (parameters.get("base_columns") or {}).items():
            base[int(raw_column)] = _resolve_value_spec(value_spec, section, None)
        for rule in _row_rules(parameters):
            kind = str(rule.get("kind") or "").strip().lower()
            if kind == "section":
                if _section_condition_matches(section, rule.get("when")):
                    rows.append(_row_from_rule(base, section, None, rule))
            elif kind == "record":
                for record in section.records:
                    if _record_matches(record, rule.get("match")):
                        rows.append(_row_from_rule(base, section, record, rule))
            elif kind == "aggregate":
                records = [
                    record
                    for record in section.records
                    if _record_matches(record, rule.get("match"))
                ]
                if records:
                    rows.append(
                        _aggregate_row(
                            base,
                            section,
                            records,
                            rule,
                            planning_columns,
                            profile_id,
                        )
                    )
            else:
                raise ValueError(
                    f"Transformation profile '{profile_id}' has unsupported row rule kind '{kind}'."
                )
    return rows


def _row_rules(parameters: dict[str, Any]) -> list[dict[str, Any]]:
    rules = parameters.get("row_rules") or []
    if not isinstance(rules, list) or not all(isinstance(rule, dict) for rule in rules):
        raise ValueError("Transformation profile row_rules must be a list of objects.")
    return rules


def _row_from_rule(
    base: list[Any],
    section: _RecordSection,
    record: dict[str, str] | None,
    rule: dict[str, Any],
) -> list[Any]:
    row = list(base)
    for raw_column, value_spec in (rule.get("columns") or {}).items():
        row[int(raw_column)] = _resolve_value_spec(value_spec, section, record)
    return row


def _aggregate_row(
    base: list[Any],
    section: _RecordSection,
    records: list[dict[str, str]],
    rule: dict[str, Any],
    planning_columns: dict[str, int],
    profile_id: str,
) -> list[Any]:
    if str(rule.get("destination") or "") != "planning_month":
        raise ValueError(f"Transformation profile '{profile_id}' has an unsupported aggregate destination.")
    key_group = str(rule.get("key_group") or "").strip()
    value_group = str(rule.get("value_group") or "").strip()
    if not key_group or not value_group:
        raise ValueError(f"Transformation profile '{profile_id}' aggregate rule requires key/value groups.")
    by_key: dict[str, int | float] = {}
    source_total: int | float = 0
    for record in records:
        key = record.get(key_group, "")
        quantity = _convert_value(record.get(value_group, ""), rule.get("value_type"))
        if not isinstance(quantity, (int, float)):
            raise ValueError(f"Transformation profile '{profile_id}' aggregate quantity must be numeric.")
        by_key[key] = _add_numbers(by_key.get(key, 0), quantity)
        source_total = _add_numbers(source_total, quantity)

    row = list(base)
    mapped_total: int | float = 0
    unmapped_keys: list[str] = []
    for key, quantity in by_key.items():
        column = _planning_column_for_month(planning_columns, key)
        if column is None:
            unmapped_keys.append(key)
            continue
        current = row[column] if isinstance(row[column], (int, float)) else 0
        row[column] = _add_numbers(current, quantity)
        mapped_total = _add_numbers(mapped_total, quantity)
    if rule.get("strict_accounting", True) and (
        unmapped_keys or not _numbers_equal(source_total, mapped_total)
    ):
        missing = ", ".join(sorted(unmapped_keys)) or "unknown"
        raise ValueError(
            f"Transformation profile '{profile_id}' could not account for section {section.key}: "
            f"planning key(s) {missing} have no Excel planning bucket "
            f"(source quantity {source_total}, mapped {mapped_total})."
        )
    return row


def _resolve_value_spec(
    value_spec: Any,
    section: _RecordSection,
    record: dict[str, str] | None,
) -> Any:
    if not isinstance(value_spec, dict):
        return value_spec
    if "literal" in value_spec:
        value: Any = value_spec.get("literal")
    elif value_spec.get("section_key"):
        value = section.key
    elif "field" in value_spec:
        value = section.fields.get(str(value_spec.get("field")), "")
    elif "group" in value_spec:
        value = (record or {}).get(str(value_spec.get("group")), "")
    else:
        value = ""
    for transform in value_spec.get("transforms") or []:
        if transform == "strip_leading_zero":
            value = str(value).lstrip("0") or "0"
        elif transform == "strip":
            value = str(value).strip()
        else:
            raise ValueError(f"Unsupported transformation profile value transform '{transform}'.")
    if value_spec.get("value_type") not in (None, ""):
        return _convert_value(value, value_spec.get("value_type"))
    return value


def _section_condition_matches(section: _RecordSection, condition: Any) -> bool:
    if not condition:
        return True
    if not isinstance(condition, dict):
        raise ValueError("Transformation profile section condition must be an object.")
    value = section.fields.get(str(condition.get("field") or ""))
    operator = str(condition.get("operator") or "truthy")
    if operator == "positive":
        return isinstance(value, (int, float)) and value > 0
    if operator == "equals":
        return value == condition.get("value")
    if operator == "truthy":
        return bool(value)
    raise ValueError(f"Unsupported transformation profile condition operator '{operator}'.")


def _record_matches(record: dict[str, str], match_spec: Any) -> bool:
    if not match_spec:
        return True
    if not isinstance(match_spec, dict):
        raise ValueError("Transformation profile record match must be an object.")
    for group, expected in match_spec.items():
        accepted = expected if isinstance(expected, list) else [expected]
        if record.get(str(group)) not in {str(value) for value in accepted}:
            return False
    return True


def _planning_month_columns(headers: list[Any], parameters: dict[str, Any]) -> dict[str, int]:
    template = parameters.get("template") or {}
    start_column = int(template.get("planning_start_column") or 0)
    backlog_headers = {
        re.sub(r"\s+", " ", str(value)).strip().casefold()
        for value in template.get("backlog_headers") or []
    }
    future_patterns = [
        re.compile(str(value), re.IGNORECASE)
        for value in template.get("future_header_patterns") or []
    ]
    columns: dict[str, int] = {}
    for index, header in enumerate(headers):
        if index < start_column or header in (None, ""):
            continue
        header_text = str(header)
        normalized_header = re.sub(r"\s+", " ", header_text).strip().casefold()
        if normalized_header in backlog_headers:
            columns["backlog"] = index
            continue
        month = _planning_header_month(header_text)
        if month is None:
            continue
        is_future = any(pattern.search(header_text) for pattern in future_patterns)
        columns[f">={month}" if is_future else month] = index
    return columns


def _planning_column_for_month(columns: dict[str, int], month: str) -> int | None:
    exact = columns.get(month)
    if exact is not None:
        return exact
    month_key = _month_key(month)
    if month_key is None:
        return None
    future_buckets = sorted(
        (_month_key(threshold[2:]), column)
        for threshold, column in columns.items()
        if threshold.startswith(">=") and _month_key(threshold[2:]) is not None
    )
    eligible = [item for item in future_buckets if item[0] is not None and month_key >= item[0]]
    if eligible:
        return eligible[-1][1]
    exact_months = sorted(
        key
        for key in (_month_key(candidate) for candidate in columns)
        if key is not None
    )
    if exact_months and month_key < exact_months[0]:
        return columns.get("backlog")
    return None


def _planning_header_month(header_text: str) -> str | None:
    numeric = re.search(r"(?<!\d)(\d{4})[-/](\d{2})(?:[-/]\d{2})?", header_text)
    if numeric:
        month = f"{numeric.group(1)}/{numeric.group(2)}"
        return month if _month_key(month) is not None else None
    named = re.search(r"(?i)\b([a-zä]+)\.?\s+(\d{4})\b", header_text)
    if not named:
        return None
    month_number = _MONTH_NAMES.get(named.group(1).casefold())
    if month_number is None:
        return None
    return f"{named.group(2)}/{month_number:02d}"


def _month_key(month: str) -> tuple[int, int] | None:
    match = re.fullmatch(r"(\d{4})/(\d{2})", str(month or "").strip())
    if not match:
        return None
    year, number = int(match.group(1)), int(match.group(2))
    return (year, number) if 1 <= number <= 12 else None


def _convert_value(value: Any, value_type: Any) -> Any:
    normalized_type = str(value_type or "string").strip().lower()
    if normalized_type in {"", "string"}:
        return str(value or "").strip()
    if normalized_type == "localized_number":
        normalized = re.sub(r"[\s.\u00a0\u202f]", "", str(value).strip()).replace(",", ".")
        number = float(normalized)
        return int(number) if number.is_integer() else number
    if normalized_type == "number":
        number = float(value)
        return int(number) if number.is_integer() else number
    raise ValueError(f"Unsupported transformation profile value type '{normalized_type}'.")


def _compile_pattern(value: Any, label: str) -> re.Pattern[str]:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Transformation profile requires a regex for {label}.")
    try:
        return re.compile(value)
    except re.error as exc:
        raise ValueError(f"Transformation profile has an invalid regex for {label}: {exc}") from exc


def _required_pattern(parameters: dict[str, Any], key: str) -> re.Pattern[str]:
    return _compile_pattern(parameters.get(key), key)


def _add_numbers(left: int | float, right: int | float) -> int | float:
    total = float(left) + float(right)
    return int(total) if total.is_integer() else total


def _numbers_equal(left: int | float, right: int | float) -> bool:
    return abs(float(left) - float(right)) <= 1e-9


def _canonical_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
