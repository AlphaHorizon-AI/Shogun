"""Profile-driven deterministic transformations for AgentFlow.

The runtime contains only generic parsing and matrix-building primitives.  All
source labels, record types, field meanings, and destination rules must be
declared by an explicit Mapping/RPA transformation profile.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from importlib.resources import files
from time import monotonic
from typing import Any

import regex

SUPPORTED_ADAPTER = "sectioned_record_matrix_v1"
PROFILE_REGEX_OPERATION_TIMEOUT_SECONDS = 1.0
PROFILE_TRANSFORMATION_TIMEOUT_SECONDS = 20.0


@dataclass(slots=True)
class DeterministicMatrixResult:
    adapter_id: str
    profile_id: str
    rows: list[list[Any]]
    resolution_states: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class _RecordSection:
    key: str
    fields: dict[str, Any] = field(default_factory=dict)
    records: list[dict[str, str]] = field(default_factory=list)
    selector_exemptions: set[str] = field(default_factory=set)
    selector_outcomes: dict[str, str] = field(default_factory=dict)
    resolution_states: list[dict[str, Any]] = field(default_factory=list)
    skip_output: bool = False


@dataclass(slots=True)
class _RecordHeaderBinding:
    """A position-sensitive mapping from raw record groups to semantic groups."""

    position: int
    source_by_target: dict[str, str]


@dataclass(slots=True)
class _RegexExecutionBudget:
    """Shared fail-closed budget for every dynamic regex in one execution."""

    profile_id: str
    started_at: float = field(default_factory=monotonic)

    def operation_timeout(self, label: str) -> float:
        remaining = PROFILE_TRANSFORMATION_TIMEOUT_SECONDS - (monotonic() - self.started_at)
        if remaining <= 0:
            raise self.timeout_error(label)
        return min(PROFILE_REGEX_OPERATION_TIMEOUT_SECONDS, remaining)

    def check_total(self, label: str) -> None:
        if monotonic() - self.started_at > PROFILE_TRANSFORMATION_TIMEOUT_SECONDS:
            raise self.timeout_error(label)

    def timeout_error(self, label: str) -> ValueError:
        return ValueError(
            f"Transformation profile '{self.profile_id}' regex operation for {label} "
            "exceeded its bounded execution budget."
        )


class _BoundedPattern:
    """Timeout-enforcing facade over a profile-supplied ``regex`` pattern."""

    __slots__ = ("_budget", "_compiled", "_label")

    def __init__(
        self,
        compiled: regex.Pattern,
        *,
        label: str,
        budget: _RegexExecutionBudget,
    ) -> None:
        self._compiled = compiled
        self._label = label
        self._budget = budget

    @property
    def groupindex(self) -> dict[str, int]:
        return self._compiled.groupindex

    def finditer(self, text: str) -> Iterator[regex.Match]:
        timeout = self._budget.operation_timeout(self._label)

        def iterate() -> Iterator[regex.Match]:
            try:
                for match in self._compiled.finditer(text, timeout=timeout):
                    self._budget.check_total(self._label)
                    yield match
            except TimeoutError as exc:
                raise self._budget.timeout_error(self._label) from exc

        return iterate()

    def search(self, text: str) -> regex.Match | None:
        timeout = self._budget.operation_timeout(self._label)
        try:
            result = self._compiled.search(text, timeout=timeout)
        except TimeoutError as exc:
            raise self._budget.timeout_error(self._label) from exc
        self._budget.check_total(self._label)
        return result


_ACTIVE_REGEX_BUDGET: ContextVar[_RegexExecutionBudget | None] = ContextVar(
    "structured_transformation_regex_budget",
    default=None,
)


@contextmanager
def _profile_regex_budget(profile_id: str) -> Iterator[_RegexExecutionBudget]:
    budget = _RegexExecutionBudget(profile_id=profile_id)
    token = _ACTIVE_REGEX_BUDGET.set(budget)
    try:
        yield budget
    finally:
        _ACTIVE_REGEX_BUDGET.reset(token)


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


def load_bundled_transformation_profile(profile_id: str) -> dict[str, Any]:
    """Load a versioned profile resource by an explicit, traversal-safe id."""

    normalized_id = str(profile_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?", normalized_id):
        raise ValueError("Bundled transformation profile id is invalid.")
    resource = files("shogun").joinpath(
        "resources",
        "transformation_profiles",
        f"{normalized_id}.json",
    )
    try:
        profile = json.loads(resource.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Bundled transformation profile '{normalized_id}' does not exist.") from exc
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"Bundled transformation profile '{normalized_id}' is invalid.") from exc
    loaded_id, _parameters = _profile_parameters(profile)
    if loaded_id != normalized_id:
        raise ValueError(f"Bundled transformation profile '{normalized_id}' declares id '{loaded_id}'.")
    return profile


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
    with _profile_regex_budget(profile_id) as budget:
        _validate_required_source_patterns(source_context, parameters, profile_id)
        headers, logical_width = _excel_template_contract(fixed_context, parameters, profile_id)
        budget.check_total("template validation")
        sections = _parse_sections(source_context, parameters, profile_id)
        sections = _order_sections(sections, parameters, profile_id)
        planning_columns = _planning_month_columns(headers, parameters, profile_id)
        rows = _build_rows(
            sections,
            logical_width,
            planning_columns,
            parameters,
            profile_id,
        )
        budget.check_total("matrix construction")
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
            resolution_states=[
                state
                for section in sections
                for state in section.resolution_states
            ],
        )


def deterministic_profile_source_units(
    profile: dict[str, Any],
    source_context: str,
) -> list[str]:
    """Split source text at the explicit profile's section boundaries."""

    profile_id, parameters = _profile_parameters(profile)
    with _profile_regex_budget(profile_id) as budget:
        pattern = _required_pattern(parameters, "section_pattern")
        matches = list(pattern.finditer(str(source_context or "")))
        if not matches:
            return [source_context] if source_context else []
        units: list[str] = []
        for index, match in enumerate(matches):
            start = 0 if index == 0 else match.start()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(source_context)
            units.append(source_context[start:end])
        budget.check_total("source unit splitting")
        return units


def expected_deterministic_matrix_rows(
    profile: dict[str, Any],
    source_context: str,
) -> int:
    """Count rows required by a profile without relying on domain heuristics."""

    profile_id, parameters = _profile_parameters(profile)
    with _profile_regex_budget(profile_id) as budget:
        sections = _parse_sections(source_context, parameters, profile_id)
        sections = _order_sections(sections, parameters, profile_id)
        total = 0
        for section in sections:
            for rule in _row_rules(parameters):
                kind = str(rule.get("kind") or "").strip().lower()
                if not _section_condition_matches(section, rule.get("when")):
                    continue
                if kind == "section":
                    total += 1
                elif kind == "record":
                    total += len(_matching_records(section, rule, profile_id))
                elif kind == "aggregate":
                    total += int(any(_record_matches(record, rule.get("match")) for record in section.records))
                else:
                    raise ValueError(f"Transformation profile '{profile_id}' has unsupported row rule kind '{kind}'.")
        budget.check_total("expected row counting")
        return total


def _profile_parameters(profile: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if not isinstance(profile, dict):
        raise ValueError("Transformation profile must be an object.")
    profile_id = str(profile.get("id") or "").strip()
    if not profile_id:
        raise ValueError("Transformation profile requires an id.")
    adapter = str(profile.get("adapter") or "").strip()
    if adapter != SUPPORTED_ADAPTER:
        raise ValueError(f"Transformation profile '{profile_id}' uses unsupported adapter '{adapter}'.")
    parameters = profile.get("parameters")
    if not isinstance(parameters, dict):
        raise ValueError(f"Transformation profile '{profile_id}' requires parameters.")
    return profile_id, parameters


def _validate_required_source_patterns(
    source_context: str,
    parameters: dict[str, Any],
    profile_id: str,
) -> None:
    for index, raw_pattern in enumerate(parameters.get("required_source_patterns") or []):
        pattern = _compile_pattern(raw_pattern, f"required source pattern {index + 1}")
        if not pattern.search(source_context or ""):
            raise ValueError(f"Runtime source does not match transformation profile '{profile_id}'.")


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
        section_text = text[match.start() : end]
        section = sections.setdefault(key, _RecordSection(key=key))
        _extract_section_fields(section, section_text, parameters, profile_id)
        _apply_section_override(section, parameters, profile_id)
        _extract_selector_fields(section, section_text, parameters, profile_id)
        header_bindings = _record_header_bindings(
            section_text,
            record_pattern,
            parameters,
            profile_id,
        )
        for record_match in record_pattern.finditer(section_text):
            record = {name: str(value or "").strip() for name, value in record_match.groupdict().items()}
            _apply_record_header_binding(
                record,
                record_match.start(),
                header_bindings,
                parameters,
                profile_id,
            )
            if record_section_key_group and record.get(record_section_key_group) != key:
                continue
            section.records.append(record)
    parsed_sections = list(sections.values())
    for section in parsed_sections:
        _apply_resolution_groups(section, parameters, profile_id)
    return parsed_sections


def _apply_section_override(
    section: _RecordSection,
    parameters: dict[str, Any],
    profile_id: str,
) -> None:
    overrides = parameters.get("section_overrides") or {}
    if not isinstance(overrides, dict):
        raise ValueError(
            f"Transformation profile '{profile_id}' section_overrides must be an object."
        )
    override = overrides.get(section.key)
    if override is None:
        return
    if not isinstance(override, dict):
        raise ValueError(
            f"Transformation profile '{profile_id}' override for section {section.key} "
            "must be an object."
        )
    fields = override.get("fields") or {}
    if not isinstance(fields, dict) or any(not str(target).strip() for target in fields):
        raise ValueError(
            f"Transformation profile '{profile_id}' override for section {section.key} "
            "has invalid fields."
        )
    section.fields.update({str(target).strip(): value for target, value in fields.items()})
    raw_exemptions = override.get("skip_selectors") or []
    if not isinstance(raw_exemptions, list) or any(
        not str(target).strip() for target in raw_exemptions
    ):
        raise ValueError(
            f"Transformation profile '{profile_id}' override for section {section.key} "
            "has invalid skip_selectors."
        )
    section.selector_exemptions.update(str(target).strip() for target in raw_exemptions)
    raw_skip_output = override.get("skip_output", False)
    if not isinstance(raw_skip_output, bool):
        raise ValueError(
            f"Transformation profile '{profile_id}' override for section {section.key} "
            "has invalid skip_output."
        )
    section.skip_output = raw_skip_output


def _record_header_bindings(
    section_text: str,
    record_pattern: _BoundedPattern,
    parameters: dict[str, Any],
    profile_id: str,
) -> list[_RecordHeaderBinding]:
    """Resolve semantic record fields from position-sensitive source headers.

    This is intentionally domain-neutral.  A profile names the header slots,
    their aliases, and which raw regex groups each slot controls.  Each record
    uses the closest preceding header, so a single input may contain sections
    whose source columns appear in different orders.
    """

    raw_layout = parameters.get("record_header_layout")
    if raw_layout in (None, {}):
        return []
    if not isinstance(raw_layout, dict):
        raise ValueError(f"Transformation profile '{profile_id}' has an invalid record header layout.")

    header_pattern = _compile_pattern(
        raw_layout.get("pattern"),
        "record header layout",
    )
    slots = raw_layout.get("slots")
    roles = raw_layout.get("roles")
    if not isinstance(slots, dict) or not slots:
        raise ValueError(f"Transformation profile '{profile_id}' record header layout requires slots.")
    if not isinstance(roles, dict) or not roles:
        raise ValueError(f"Transformation profile '{profile_id}' record header layout requires roles.")
    if len(slots) != len(roles):
        raise ValueError(
            f"Transformation profile '{profile_id}' record header layout must map every slot to exactly one role."
        )

    aliases: dict[str, str] = {}
    role_targets: dict[str, dict[str, str]] = {}
    for raw_role, raw_spec in roles.items():
        role = str(raw_role).strip()
        if not role or not isinstance(raw_spec, dict):
            raise ValueError(f"Transformation profile '{profile_id}' has an invalid record header role.")
        raw_aliases = raw_spec.get("aliases") or []
        targets = raw_spec.get("targets")
        if not isinstance(raw_aliases, list) or not raw_aliases or not isinstance(targets, dict):
            raise ValueError(
                f"Transformation profile '{profile_id}' record header role '{role}' requires aliases and targets."
            )
        normalized_targets = {str(field).strip(): str(target).strip() for field, target in targets.items()}
        if not normalized_targets or any(not field or not target for field, target in normalized_targets.items()):
            raise ValueError(f"Transformation profile '{profile_id}' record header role '{role}' has invalid targets.")
        role_targets[role] = normalized_targets
        for raw_alias in raw_aliases:
            alias = _canonical_header(raw_alias)
            if not alias:
                raise ValueError(
                    f"Transformation profile '{profile_id}' record header role '{role}' has an empty alias."
                )
            existing = aliases.get(alias)
            if existing is not None and existing != role:
                raise ValueError(
                    f"Transformation profile '{profile_id}' has ambiguous record header alias '{raw_alias}'."
                )
            aliases[alias] = role

    normalized_slots: dict[str, dict[str, str]] = {}
    for raw_slot, raw_sources in slots.items():
        slot = str(raw_slot).strip()
        if slot not in header_pattern.groupindex or not isinstance(raw_sources, dict):
            raise ValueError(
                f"Transformation profile '{profile_id}' record header slot '{slot}' is not a named header group."
            )
        sources = {str(field).strip(): str(source).strip() for field, source in raw_sources.items()}
        if not sources or any(
            not field or not source or source not in record_pattern.groupindex for field, source in sources.items()
        ):
            raise ValueError(
                f"Transformation profile '{profile_id}' record header slot '{slot}' references an invalid record group."
            )
        normalized_slots[slot] = sources

    bindings: list[_RecordHeaderBinding] = []
    for header_match in header_pattern.finditer(section_text):
        used_roles: set[str] = set()
        source_by_target: dict[str, str] = {}
        for slot, sources in normalized_slots.items():
            label = str(header_match.group(slot) or "").strip()
            role = aliases.get(_canonical_header(label))
            if role is None:
                raise ValueError(f"Transformation profile '{profile_id}' found unknown record header label '{label}'.")
            if role in used_roles:
                raise ValueError(
                    f"Transformation profile '{profile_id}' found an ambiguous record "
                    f"header: role '{role}' occurs more than once."
                )
            used_roles.add(role)
            targets = role_targets[role]
            if set(sources) != set(targets):
                raise ValueError(
                    f"Transformation profile '{profile_id}' record header role '{role}' "
                    "does not define the same fields as its slot."
                )
            for field_name, source in sources.items():
                target = targets[field_name]
                existing_source = source_by_target.get(target)
                if existing_source is not None and existing_source != source:
                    raise ValueError(
                        f"Transformation profile '{profile_id}' maps record header target '{target}' more than once."
                    )
                source_by_target[target] = source
        if used_roles != set(role_targets):
            missing = ", ".join(sorted(set(role_targets) - used_roles))
            raise ValueError(f"Transformation profile '{profile_id}' record header is missing role(s): {missing}.")
        bindings.append(
            _RecordHeaderBinding(
                position=header_match.end(),
                source_by_target=source_by_target,
            )
        )

    if not bindings and raw_layout.get("required", True):
        raise ValueError(f"Transformation profile '{profile_id}' found no required record header layout.")
    return bindings


def _apply_record_header_binding(
    record: dict[str, str],
    record_position: int,
    bindings: list[_RecordHeaderBinding],
    parameters: dict[str, Any],
    profile_id: str,
) -> None:
    if not parameters.get("record_header_layout"):
        return
    binding = next(
        (candidate for candidate in reversed(bindings) if candidate.position <= record_position),
        None,
    )
    if binding is None:
        raise ValueError(f"Transformation profile '{profile_id}' found a record before its required header layout.")
    for target, source in binding.source_by_target.items():
        if target in record and target != source:
            raise ValueError(
                f"Transformation profile '{profile_id}' record header target '{target}' "
                "conflicts with an existing record group."
            )
        record[target] = record.get(source, "")


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
                    f"Transformation profile '{profile_id}' section field '{target}' lacks group '{group}'."
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
        if not target:
            raise ValueError(f"Transformation profile '{profile_id}' selector requires a target.")
        if target in section.selector_exemptions:
            continue
        if not _section_condition_matches(section, rule.get("when")):
            continue
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
                    f"Transformation profile '{profile_id}' selector '{target}' lacks scope group '{scope_group}'."
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
        if rule.get("distinct"):
            values = list(dict.fromkeys(values))
        for index, raw_pattern in enumerate(rule.get("preferred_value_patterns") or []):
            pattern = _compile_pattern(
                raw_pattern,
                f"selector '{target}' preferred value pattern {index + 1}",
                flags=regex.IGNORECASE,
            )
            preferred = [value for value in values if pattern.search(str(value))]
            if preferred and len(preferred) < len(values):
                values = preferred
        minimum_matches = int(rule.get("minimum_matches") or 0)
        raw_maximum = rule.get("maximum_matches")
        maximum_matches = None if raw_maximum in (None, "") else int(raw_maximum)
        if minimum_matches < 0 or (maximum_matches is not None and maximum_matches < minimum_matches):
            raise ValueError(
                f"Transformation profile '{profile_id}' selector '{target}' has invalid match cardinality."
            )
        cardinality_mismatch = len(values) < minimum_matches or (
            maximum_matches is not None and len(values) > maximum_matches
        )
        mismatch_policy = str(rule.get("on_cardinality_mismatch") or "error").strip().lower()
        if mismatch_policy not in {"error", "preserve"}:
            raise ValueError(
                f"Transformation profile '{profile_id}' selector '{target}' has unsupported "
                f"on_cardinality_mismatch policy '{mismatch_policy}'."
            )
        if cardinality_mismatch and mismatch_policy == "error":
            maximum_label = "unbounded" if maximum_matches is None else str(maximum_matches)
            raise ValueError(
                f"Transformation profile '{profile_id}' selector '{target}' in section "
                f"{section.key} expected {minimum_matches}..{maximum_label} match(es), "
                f"found {len(values)}."
            )
        if cardinality_mismatch:
            section.selector_outcomes[target] = "missing" if not values else "ambiguous"
            # A single value remains source-grounded even when a profile asks for
            # more than one. Multiple values cannot safely feed a scalar field.
            if len(values) == 1:
                _store_aggregated_field(
                    section.fields,
                    target,
                    values,
                    str(rule.get("aggregate") or "first"),
                )
            continue
        section.selector_outcomes[target] = "resolved" if values else "empty"
        if values:
            _store_aggregated_field(section.fields, target, values, str(rule.get("aggregate") or "first"))


def _apply_resolution_groups(
    section: _RecordSection,
    parameters: dict[str, Any],
    profile_id: str,
) -> None:
    """Classify a profile-declared set of semantic fields without inventing values."""

    groups = parameters.get("resolution_groups") or []
    if not isinstance(groups, list) or any(not isinstance(group, dict) for group in groups):
        raise ValueError(
            f"Transformation profile '{profile_id}' resolution_groups must be a list of objects."
        )
    for index, group in enumerate(groups):
        name = str(group.get("name") or f"resolution_{index + 1}").strip()
        raw_targets = group.get("targets")
        if (
            not name
            or not isinstance(raw_targets, list)
            or not raw_targets
            or any(not str(target).strip() for target in raw_targets)
        ):
            raise ValueError(
                f"Transformation profile '{profile_id}' resolution group {index + 1} is invalid."
            )
        targets = [str(target).strip() for target in raw_targets]
        if len(set(targets)) != len(targets):
            raise ValueError(
                f"Transformation profile '{profile_id}' resolution group '{name}' repeats a target."
            )
        status_target = str(group.get("status_target") or "").strip()
        if not status_target:
            raise ValueError(
                f"Transformation profile '{profile_id}' resolution group '{name}' requires status_target."
            )
        review_target = str(group.get("requires_review_target") or "").strip()
        applies = _section_condition_matches(section, group.get("when"))
        present = [target for target in targets if section.fields.get(target) not in (None, "", [])]
        if not applies:
            status = "NOT_APPLICABLE"
        elif len(present) == len(targets):
            status = "RESOLVED"
        elif present:
            status = "PARTIAL"
        else:
            status = "UNRESOLVED"
        requires_review = status in {"PARTIAL", "UNRESOLVED"}
        target_states = {
            target: (
                "not_applicable"
                if not applies
                else "resolved"
                if target in present
                else section.selector_outcomes.get(target, "missing")
            )
            for target in targets
        }
        section.fields[status_target] = status
        if review_target:
            section.fields[review_target] = requires_review
        section.resolution_states.append(
            {
                "section_key": section.key,
                "name": name,
                "status": status,
                "requires_manual_validation": requires_review,
                "targets": target_states,
            }
        )


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
        raise ValueError(f"Transformation profile '{profile_id}' requires at least {minimum_columns} template columns.")
    for raw_index, accepted in (template.get("expected_headers") or {}).items():
        index = int(raw_index)
        aliases = accepted if isinstance(accepted, list) else [accepted]
        if index >= logical_width or _canonical_header(headers[index]) not in {
            _canonical_header(alias) for alias in aliases
        }:
            raise ValueError(f"Transformation profile '{profile_id}' does not match template column {index + 1}.")
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
            if not _section_condition_matches(section, rule.get("when")):
                continue
            if kind == "section":
                rows.append(
                    _row_from_rule(
                        base,
                        section,
                        None,
                        rule,
                        planning_columns,
                        profile_id,
                    )
                )
            elif kind == "record":
                for record in _matching_records(section, rule, profile_id):
                    rows.append(
                        _row_from_rule(
                            base,
                            section,
                            record,
                            rule,
                            planning_columns,
                            profile_id,
                        )
                    )
            elif kind == "aggregate":
                records = [record for record in section.records if _record_matches(record, rule.get("match"))]
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
                raise ValueError(f"Transformation profile '{profile_id}' has unsupported row rule kind '{kind}'.")
    return rows


def _row_rules(parameters: dict[str, Any]) -> list[dict[str, Any]]:
    rules = parameters.get("row_rules") or []
    if not isinstance(rules, list) or not all(isinstance(rule, dict) for rule in rules):
        raise ValueError("Transformation profile row_rules must be a list of objects.")
    return rules


def _matching_records(
    section: _RecordSection,
    rule: dict[str, Any],
    profile_id: str,
) -> list[dict[str, str]]:
    records = [record for record in section.records if _record_matches(record, rule.get("match"))]
    raw_identity = rule.get("deduplicate_by")
    if raw_identity in (None, []):
        return records
    if not isinstance(raw_identity, list) or not raw_identity:
        raise ValueError(f"Transformation profile '{profile_id}' record deduplicate_by must be a non-empty list.")
    identity_specs: list[dict[str, Any]] = []
    for raw_spec in raw_identity:
        spec = {"group": raw_spec} if isinstance(raw_spec, str) else raw_spec
        if not isinstance(spec, dict) or not str(spec.get("group") or "").strip():
            raise ValueError(
                f"Transformation profile '{profile_id}' record deduplicate_by contains an invalid identity group."
            )
        identity_specs.append(spec)
    identity_groups = [str(spec["group"]).strip() for spec in identity_specs]
    if len(set(identity_groups)) != len(identity_groups):
        raise ValueError(
            f"Transformation profile '{profile_id}' record deduplicate_by contains a repeated identity group."
        )

    unique: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for record in records:
        missing = [group for group in identity_groups if not str(record.get(group) or "").strip()]
        if missing:
            raise ValueError(
                f"Transformation profile '{profile_id}' cannot deduplicate a record in "
                f"section {section.key}: stable identity group(s) "
                f"{', '.join(missing)} are empty."
            )
        identity = tuple(str(_resolve_value_spec(spec, section, record)).strip() for spec in identity_specs)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(record)
    return unique


def _row_from_rule(
    base: list[Any],
    section: _RecordSection,
    record: dict[str, str] | None,
    rule: dict[str, Any],
    planning_columns: dict[str, int],
    profile_id: str,
) -> list[Any]:
    row = list(base)
    for raw_column, value_spec in (rule.get("columns") or {}).items():
        row[int(raw_column)] = _resolve_value_spec(value_spec, section, record)
    planning = rule.get("planning")
    if planning not in (None, {}):
        if record is None or not isinstance(planning, dict):
            raise ValueError(f"Transformation profile '{profile_id}' record planning rule is invalid.")
        _map_record_to_planning_column(
            row,
            section,
            record,
            planning,
            planning_columns,
            profile_id,
        )
    return row


def _map_record_to_planning_column(
    row: list[Any],
    section: _RecordSection,
    record: dict[str, str],
    planning: dict[str, Any],
    planning_columns: dict[str, int],
    profile_id: str,
) -> None:
    if str(planning.get("destination") or "planning_month") != "planning_month":
        raise ValueError(f"Transformation profile '{profile_id}' has an unsupported record planning destination.")
    key_group = str(planning.get("key_group") or "").strip()
    value_group = str(planning.get("value_group") or "").strip()
    if not key_group or not value_group:
        raise ValueError(f"Transformation profile '{profile_id}' record planning requires key/value groups.")
    key = record.get(key_group, "")
    quantity = _convert_value(record.get(value_group, ""), planning.get("value_type"))
    if not isinstance(quantity, (int, float)):
        raise ValueError(f"Transformation profile '{profile_id}' record planning quantity must be numeric.")
    column = _planning_column_for_month(planning_columns, key)
    if column is None:
        if planning.get("strict_accounting", True):
            raise ValueError(
                f"Transformation profile '{profile_id}' could not account for section {section.key}: "
                f"planning key {key or 'unknown'} has no Excel planning bucket "
                f"(source quantity {quantity}, mapped 0)."
            )
        return
    current = row[column] if isinstance(row[column], (int, float)) else 0
    row[column] = _add_numbers(current, quantity)


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
    if rule.get("strict_accounting", True) and (unmapped_keys or not _numbers_equal(source_total, mapped_total)):
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
    if "case" in value_spec:
        cases = value_spec.get("case")
        if not isinstance(cases, list) or not cases or any(
            not isinstance(candidate, dict) or "value" not in candidate
            for candidate in cases
        ):
            raise ValueError("Transformation profile case requires a non-empty list of value cases.")
        value = _resolve_value_spec(value_spec.get("default", {}), section, record)
        for candidate in cases:
            if _section_condition_matches(section, candidate.get("when")):
                value = _resolve_value_spec(candidate["value"], section, record)
                break
    elif "coalesce" in value_spec:
        candidates = value_spec.get("coalesce")
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("Transformation profile coalesce requires a non-empty value list.")
        value = ""
        for candidate in candidates:
            resolved = _resolve_value_spec(candidate, section, record)
            if resolved not in (None, "", []):
                value = resolved
                break
    elif "join" in value_spec:
        join_spec = value_spec.get("join")
        if not isinstance(join_spec, dict):
            raise ValueError("Transformation profile join requires an object.")
        value_specs = join_spec.get("values")
        if not isinstance(value_specs, list) or not value_specs:
            raise ValueError("Transformation profile join requires a non-empty value list.")
        resolved_values = [_resolve_value_spec(item, section, record) for item in value_specs]
        missing = [item for item in resolved_values if item in (None, "", [])]
        if missing and join_spec.get("require_all", False):
            value = ""
        else:
            separator = str(join_spec.get("separator") if "separator" in join_spec else " ")
            value = separator.join(str(item) for item in resolved_values if item not in (None, "", []))
    elif "literal" in value_spec:
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
    if "all" in condition:
        conditions = condition.get("all")
        if not isinstance(conditions, list) or not conditions:
            raise ValueError("Transformation profile 'all' condition requires a non-empty list.")
        return all(_section_condition_matches(section, item) for item in conditions)
    if "any" in condition:
        conditions = condition.get("any")
        if not isinstance(conditions, list) or not conditions:
            raise ValueError("Transformation profile 'any' condition requires a non-empty list.")
        return any(_section_condition_matches(section, item) for item in conditions)
    if "not" in condition:
        return not _section_condition_matches(section, condition.get("not"))
    value = section.fields.get(str(condition.get("field") or ""))
    operator = str(condition.get("operator") or "truthy").strip().lower()
    if operator == "positive":
        return isinstance(value, (int, float)) and value > 0
    if operator == "equals":
        return value == condition.get("value")
    if operator == "in":
        accepted = condition.get("values")
        if not isinstance(accepted, list):
            raise ValueError("Transformation profile 'in' condition requires a values list.")
        return value in accepted
    if operator in {"contains", "not_contains"}:
        expected = str(condition.get("value") or "").casefold()
        matched = bool(expected) and expected in str(value or "").casefold()
        return matched if operator == "contains" else not matched
    if operator in {"matches", "not_matches"}:
        pattern = _compile_pattern(
            condition.get("pattern"),
            "section condition",
            flags=regex.IGNORECASE,
        )
        matched = pattern.search(str(value or "")) is not None
        return matched if operator == "matches" else not matched
    if operator == "truthy":
        return bool(value)
    raise ValueError(f"Unsupported transformation profile condition operator '{operator}'.")


def _order_sections(
    sections: list[_RecordSection],
    parameters: dict[str, Any],
    profile_id: str,
) -> list[_RecordSection]:
    sections = [section for section in sections if not section.skip_output]
    order_spec = parameters.get("section_order")
    if not order_spec:
        return sections
    if not isinstance(order_spec, dict):
        raise ValueError(f"Transformation profile '{profile_id}' section_order must be an object.")

    raw_groups = order_spec.get("groups") or []
    if not isinstance(raw_groups, list) or not all(isinstance(group, dict) for group in raw_groups):
        raise ValueError(f"Transformation profile '{profile_id}' section_order groups are invalid.")
    grouped: list[list[_RecordSection]] = [[] for _ in raw_groups]
    unmatched: list[_RecordSection] = []
    target_field = str(order_spec.get("target_field") or "").strip()
    for section in sections:
        matched_group = None
        for index, group in enumerate(raw_groups):
            if _section_condition_matches(section, group.get("when")):
                matched_group = index
                if target_field:
                    section.fields[target_field] = str(group.get("name") or index)
                break
        if matched_group is None:
            unmatched.append(section)
        else:
            grouped[matched_group].append(section)

    unmatched_mode = str(order_spec.get("unmatched") or "preserve").strip().lower()
    if unmatched and unmatched_mode == "error":
        preview = ", ".join(section.key for section in unmatched[:10])
        raise ValueError(f"Transformation profile '{profile_id}' could not classify section(s): {preview}.")
    if unmatched_mode not in {"preserve", "error"}:
        raise ValueError(
            f"Transformation profile '{profile_id}' has unsupported section_order unmatched mode '{unmatched_mode}'."
        )

    ordered = [section for group in grouped for section in group]
    ordered.extend(unmatched)
    dependency_spec = order_spec.get("dependencies_before")
    if not dependency_spec:
        return ordered
    if not isinstance(dependency_spec, dict):
        raise ValueError(f"Transformation profile '{profile_id}' dependencies_before must be an object.")
    fields = dependency_spec.get("fields")
    if not isinstance(fields, list) or not fields or not all(str(field).strip() for field in fields):
        raise ValueError(f"Transformation profile '{profile_id}' dependencies_before requires fields.")
    by_key = {section.key: section for section in sections}
    result: list[_RecordSection] = []
    emitted: set[str] = set()
    visiting: set[str] = set()

    def emit(section: _RecordSection) -> None:
        if section.key in emitted:
            return
        if section.key in visiting:
            raise ValueError(
                f"Transformation profile '{profile_id}' found a section dependency cycle at {section.key}."
            )
        visiting.add(section.key)
        for field_name in fields:
            dependency_key = str(section.fields.get(str(field_name)) or "").strip()
            if not dependency_key:
                continue
            dependency = by_key.get(dependency_key)
            if dependency is None:
                if str(dependency_spec.get("missing") or "ignore").strip().lower() == "error":
                    raise ValueError(
                        f"Transformation profile '{profile_id}' section {section.key} references "
                        f"missing dependency {dependency_key}."
                    )
                continue
            emit(dependency)
        visiting.remove(section.key)
        emitted.add(section.key)
        result.append(section)

    for section in ordered:
        emit(section)
    return result


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


def _planning_month_columns(
    headers: list[Any],
    parameters: dict[str, Any],
    profile_id: str,
) -> dict[str, int]:
    template = parameters.get("template") or {}
    start_column = int(template.get("planning_start_column") or 0)
    backlog_headers = {
        re.sub(r"\s+", " ", str(value)).strip().casefold() for value in template.get("backlog_headers") or []
    }
    future_patterns = [
        _compile_pattern(
            value,
            f"future header pattern {index + 1}",
            flags=regex.IGNORECASE,
        )
        for index, value in enumerate(template.get("future_header_patterns") or [])
    ]
    columns: dict[str, int] = {}
    for index, header in enumerate(headers):
        if index < start_column or header in (None, ""):
            continue
        header_text = str(header)
        normalized_header = re.sub(r"\s+", " ", header_text).strip().casefold()
        if normalized_header in backlog_headers:
            if "backlog" in columns:
                raise ValueError(f"Transformation profile '{profile_id}' found more than one backlog column.")
            columns["backlog"] = index
            continue
        month = _planning_header_month(header_text)
        if month is None:
            continue
        is_future = any(pattern.search(header_text) for pattern in future_patterns)
        bucket = f">={month}" if is_future else month
        if bucket in columns:
            raise ValueError(f"Transformation profile '{profile_id}' found ambiguous planning header '{header_text}'.")
        columns[bucket] = index
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
    exact_months = sorted(key for key in (_month_key(candidate) for candidate in columns) if key is not None)
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


def _compile_pattern(
    value: Any,
    label: str,
    *,
    flags: int = 0,
) -> _BoundedPattern:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Transformation profile requires a regex for {label}.")
    # Static profile validation imports this compiler to inspect group names
    # without executing the pattern.  Runtime entry points always install one
    # shared profile budget; the standalone budget preserves that compile-only
    # validation API without creating an unbounded execution path.
    budget = _ACTIVE_REGEX_BUDGET.get() or _RegexExecutionBudget(profile_id="schema_validation")
    try:
        compiled = regex.compile(value, flags)
    except regex.error as exc:
        raise ValueError(f"Transformation profile has an invalid regex for {label}: {exc}") from exc
    return _BoundedPattern(compiled, label=label, budget=budget)


def _required_pattern(parameters: dict[str, Any], key: str) -> _BoundedPattern:
    return _compile_pattern(parameters.get(key), key)


def _add_numbers(left: int | float, right: int | float) -> int | float:
    total = float(left) + float(right)
    return int(total) if total.is_integer() else total


def _numbers_equal(left: int | float, right: int | float) -> bool:
    return abs(float(left) - float(right)) <= 1e-9


def _canonical_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())
