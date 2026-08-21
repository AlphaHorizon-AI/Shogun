"""Domain-neutral regression tests for the sectioned matrix adapter."""

from __future__ import annotations

import json
from copy import deepcopy
from time import monotonic

import pytest

from shogun.engine import flow_engine
from shogun.services.structured_transformations import (
    deterministic_profile_source_units,
    expected_deterministic_matrix_rows,
    load_bundled_transformation_profile,
    try_deterministic_matrix_transform,
)

NUMBER_PATTERN = r"[+-]?(?:\d{1,3}(?:[ .\u00a0\u202f]\d{3})+|\d+)(?:,\d+)?"
PROFILE = {
    "id": "synthetic_sectioned_report_v1",
    "adapter": "sectioned_record_matrix_v1",
    "parameters": {
        "required_source_patterns": [
            r"(?m)^Entity: \S+$",
            r"(?m)^[PD] \S+ ",
        ],
        "section_pattern": r"(?m)^Entity: (?P<section_id>\S+)$",
        "section_key_group": "section_id",
        "section_fields": [
            {
                "target": "label",
                "pattern": r"(?m)^Label: (?P<value>.+)$",
                "group": "value",
                "aggregate": "first",
            },
            {
                "target": "on_hand",
                "pattern": rf"(?m)^On hand: (?P<value>{NUMBER_PATTERN})$",
                "group": "value",
                "value_type": "localized_number",
                "aggregate": "max",
            },
        ],
        "selector_fields": [
            {
                "target": "primary_component",
                "scope_pattern": r"(?ims)^Components:\s*\n(?P<body>.*?)^End Components$",
                "line_pattern": r"(?m)^(?P<value>\S+)\s+(?P<text>.+)$",
                "include_terms": ["raw material"],
                "exclude_terms": ["packaging"],
                "aggregate": "first",
            }
        ],
        "record_pattern": (
            r"(?m)^(?P<kind>P|D)\s+"
            r"(?P<entity>\S+)\s+"
            r"(?P<reference>\S+)\s+"
            r"(?P<period_1_month>\d{4}/\d{2})\s+"
            r"(?P<period_2_month>\d{4}/\d{2})\s+"
            rf"(?P<quantity>{NUMBER_PATTERN})$"
        ),
        "record_section_key_group": "entity",
        "record_header_layout": {
            "pattern": (
                r"(?m)^Columns: (?P<period_1_role>Promise|Need) "
                r"(?P<period_2_role>Promise|Need)$"
            ),
            "required": True,
            "slots": {
                "period_1_role": {"month": "period_1_month"},
                "period_2_role": {"month": "period_2_month"},
            },
            "roles": {
                "promise": {
                    "aliases": ["Promise"],
                    "targets": {"month": "promise_month"},
                },
                "need": {
                    "aliases": ["Need"],
                    "targets": {"month": "need_month"},
                },
            },
        },
        "template": {
            "minimum_columns": 8,
            "expected_headers": {
                "1": ["Entity ID"],
                "3": ["Reference"],
            },
            "planning_start_column": 5,
            "backlog_headers": ["Backlog"],
            "future_header_patterns": [r"^>=", r"future"],
        },
        "base_columns": {
            "0": {"field": "label"},
            "1": {"section_key": True},
            "2": {"field": "primary_component"},
        },
        "row_rules": [
            {
                "kind": "section",
                "when": {"field": "on_hand", "operator": "positive"},
                "columns": {
                    "3": {"literal": "On hand"},
                    "4": {"field": "on_hand"},
                },
            },
            {
                "kind": "record",
                "match": {"kind": "P"},
                "deduplicate_by": [
                    {"group": "entity"},
                    {"group": "reference", "transforms": ["strip_leading_zero"]},
                ],
                "columns": {
                    "3": {"group": "reference", "transforms": ["strip_leading_zero"]},
                    "4": {"group": "quantity", "value_type": "localized_number"},
                },
            },
            {
                "kind": "aggregate",
                "match": {"kind": "D"},
                "key_group": "need_month",
                "value_group": "quantity",
                "value_type": "localized_number",
                "destination": "planning_month",
                "strict_accounting": True,
            },
        ],
    },
}

TASK = "Extract every record and section into the supplied spreadsheet contract."

FIXED_CONTEXT = """[FILE TEMPLATE CONTRACT]
Format: xlsx
[MACHINE-READABLE TEMPLATE MANIFEST]
{"kind":"excel","sheets":[{"logical_columns":8,"preview_rows":[
  ["Label","Entity ID","Component","Reference","Quantity","Backlog",
   "2026-08-01T00:00:00",">= 2026-09-01T00:00:00"]
]}]}
"""

SOURCE = """Entity: ITEM-A
Label: Example widget
On hand: 2,0
Components:
RAW-1 primary raw material
PACK-1 packaging insert
End Components
Columns: Promise Need
P ITEM-A 000100 2026/07 2026/08 10,0
P ITEM-A 100 2026/07 2026/08 10,0
D ITEM-A request-1 2026/05 2026/06 5,0
D ITEM-A request-2 2026/08 2026/08 7,0
D ITEM-A request-3 2027/01 2027/01 9,0
"""


def _transform(source: str = SOURCE, fixed_context: str = FIXED_CONTEXT):
    return try_deterministic_matrix_transform(
        profile=PROFILE,
        source_context=source,
        fixed_context=fixed_context,
    )


def test_generic_adapter_builds_fixed_width_rows_and_deduplicates_stable_identity():
    result = _transform()

    assert result.adapter_id == "sectioned_record_matrix_v1"
    assert result.profile_id == "synthetic_sectioned_report_v1"
    assert len(result.rows) == 3
    assert all(len(row) == 8 for row in result.rows)

    stock, production, demand = result.rows
    assert stock[:5] == ["Example widget", "ITEM-A", "RAW-1", "On hand", 2]
    assert production[:5] == ["Example widget", "ITEM-A", "RAW-1", "100", 10]
    assert demand[5:] == [5, 7, 9]


def test_generic_adapter_parses_grouped_localized_numbers():
    source = SOURCE.replace("On hand: 2,0", "On hand: 1\u202f234,5").replace(
        "D ITEM-A request-2 2026/08 2026/08 7,0",
        "D ITEM-A request-2 2026/08 2026/08 1 200,5",
    )

    stock, _production, demand = _transform(source).rows
    assert stock[4] == 1234.5
    assert demand[6] == 1200.5


def test_generic_adapter_uses_semantic_header_roles_when_columns_are_reversed():
    source = SOURCE.replace("Columns: Promise Need", "Columns: Need Promise")
    for before, after in (
        ("2026/07 2026/08", "2026/08 2026/07"),
        ("2026/05 2026/06", "2026/06 2026/05"),
        ("2026/08 2026/08", "2026/08 2026/08"),
        ("2027/01 2027/01", "2027/01 2027/01"),
    ):
        source = source.replace(before, after)

    demand = _transform(source).rows[-1]
    assert demand[5:] == [5, 7, 9]


def test_generic_adapter_applies_closest_preceding_header_to_each_record_block():
    source = SOURCE.replace(
        "D ITEM-A request-2 2026/08 2026/08 7,0",
        "Columns: Need Promise\nD ITEM-A request-2 2026/08 2026/08 7,0",
    ).replace(
        "D ITEM-A request-3 2027/01 2027/01 9,0",
        "D ITEM-A request-3 2027/01 2027/01 9,0",
    )

    demand = _transform(source).rows[-1]
    assert demand[5:] == [5, 7, 9]


def test_generic_adapter_fails_closed_for_missing_or_ambiguous_record_header():
    with pytest.raises(ValueError, match="no required record header layout"):
        _transform(SOURCE.replace("Columns: Promise Need\n", ""))

    with pytest.raises(ValueError, match="ambiguous record header.*need.*more than once"):
        _transform(SOURCE.replace("Columns: Promise Need", "Columns: Need Need"))


def test_generic_adapter_fails_closed_when_template_cannot_account_for_month():
    source = SOURCE.replace(
        "D ITEM-A request-1 2026/05 2026/06 5,0",
        "D ITEM-A request-1 2026/05 2035/06 5,0",
    )
    fixed_context = FIXED_CONTEXT.replace(">= 2026-09-01T00:00:00", "2026-09-01T00:00:00")

    with pytest.raises(ValueError, match="2035/06.*no Excel planning bucket"):
        _transform(source, fixed_context)


def test_generic_adapter_fails_closed_for_source_or_template_mismatch():
    with pytest.raises(ValueError, match="Runtime source does not match"):
        _transform(SOURCE.replace("Entity: ITEM-A", "Object: ITEM-A"))

    with pytest.raises(ValueError, match="does not match template column 2"):
        _transform(fixed_context=FIXED_CONTEXT.replace("Entity ID", "Object ID"))


def test_generic_source_units_and_expected_row_count_are_profile_driven():
    second = SOURCE.replace("ITEM-A", "ITEM-B").replace("Example widget", "Second widget")
    combined = f"{SOURCE}\n{second}"

    units = deterministic_profile_source_units(PROFILE, combined)
    assert len(units) == 2
    assert expected_deterministic_matrix_rows(PROFILE, combined) == 6
    assert flow_engine._minimum_matrix_rows_for_source(combined, TASK, {
        "_transformation_profiles": [PROFILE]
    }) == (6, 6, "profile-required row(s)")


@pytest.mark.asyncio
async def test_samurai_executes_generic_adapter_without_model_routing(monkeypatch):
    async def unexpected_route(*_args, **_kwargs):
        raise AssertionError("deterministic transformation must not route to a model")

    monkeypatch.setattr(flow_engine, "_resolve_task_llm_chain", unexpected_route)
    progress: list[tuple[int, int]] = []

    async def report(completed: int, total: int):
        progress.append((completed, total))

    output = await flow_engine._exec_samurai(
        {"task_description": TASK, "_transformation_profiles": [PROFILE]},
        SOURCE,
        progress_callback=report,
        fixed_context_str=FIXED_CONTEXT,
    )

    assert json.loads(output) == _transform().rows
    assert progress[-1][0] == progress[-1][1]


def test_bundled_profile_loader_rejects_missing_and_traversal_ids():
    with pytest.raises(ValueError, match="does not exist"):
        load_bundled_transformation_profile("synthetic_private_profile_v1")

    with pytest.raises(ValueError, match="profile id is invalid"):
        load_bundled_transformation_profile("../synthetic_private_profile_v1")


@pytest.mark.parametrize(
    "pathological_pattern",
    [
        r"(a+){20}$",
        r"(?:a|aa){40}$",
        r"(?:a{1,3}){40}$",
    ],
)
def test_dynamic_fixed_repeat_patterns_fail_closed_within_operation_budget(
    pathological_pattern,
):
    profile = deepcopy(PROFILE)
    profile["parameters"]["required_source_patterns"] = [r"a"]
    profile["parameters"]["section_pattern"] = pathological_pattern
    adversarial_source = ("a" * 100_000) + "!"

    started = monotonic()
    with pytest.raises(ValueError, match="regex operation.*bounded execution budget"):
        try_deterministic_matrix_transform(
            profile=profile,
            source_context=adversarial_source,
            fixed_context=FIXED_CONTEXT,
        )

    assert monotonic() - started < 2.5


def test_large_valid_sap_like_profile_transformation_remains_supported():
    section_count = 1_500
    large_source = "\n".join(
        SOURCE.replace("ITEM-A", f"ITEM-{index:05d}").replace(
            "Example widget",
            f"Example widget {index}",
        )
        for index in range(section_count)
    )

    result = try_deterministic_matrix_transform(
        profile=PROFILE,
        source_context=large_source,
        fixed_context=FIXED_CONTEXT,
    )

    assert len(large_source) > 500_000
    assert len(result.rows) == section_count * 3
    assert result.rows[0][1] == "ITEM-00000"
    assert result.rows[-1][1] == f"ITEM-{section_count - 1:05d}"
