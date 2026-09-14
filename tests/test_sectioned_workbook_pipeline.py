"""Tests for the generic profile-driven sectioned workbook pipeline.

Includes:
1. Canonical content_hash sync for private profile envelopes.
2. Schema validation of parameters.workbook_update.
3. Unrelated domain test (Facility Maintenance & Equipment Inspection).
4. Strict number conversion semantics.
5. Strict path aliasing prevention.
"""

from __future__ import annotations

import datetime

import openpyxl
import pytest

from shogun.services.sectioned_workbook_pipeline import (
    SectionedLayoutParser,
    run_sectioned_workbook_pipeline,
)
from shogun.services.sectioned_workbook_updater import (
    SafeWorkbookUpdater,
    validate_workbook_update_profile,
)
from shogun.services.structured_transformations import (
    _convert_value,
)


def test_validate_workbook_update_profile_bounds_and_unknown_keys():
    valid_profile = {
        "id": "test_profile",
        "parameters": {
            "workbook_update": {
                "header_row": 1,
                "data_start_row": 3,
                "section_key_column": 2,
                "planning_start_column": 10,
                "expected_headers": {"2": ["Artikel"], "10": "Planning"},
                "section_rules": [
                    {
                        "name": "stock",
                        "match_column": 5,
                        "value_column": 6,
                        "match_pattern": r"^Stock\s+{section_key}$",
                        "insert_row_values": {"2": {"section_key": True}},
                    }
                ],
                "record_rules": [
                    {
                        "id": "order",
                        "match": {"kind": "work_order"},
                        "reference_column": 5,
                        "fill_blank_quantity_column": 6,
                        "fill_blank_date_column": 10,
                        "insert_row_values": {"2": {"section_key": True}},
                    }
                ],
            }
        },
    }
    # Valid profile should pass without exception
    validate_workbook_update_profile(valid_profile)

    # 1. Non-dict profile
    with pytest.raises(ValueError, match="must be a dictionary"):
        validate_workbook_update_profile("not_a_dict")

    # 2. Unknown key in workbook_update
    bad_key = {
        "parameters": {
            "workbook_update": {
                "section_key_column": 2,
                "invalid_unknown_key": True,
            }
        }
    }
    with pytest.raises(ValueError, match="Unsupported key"):
        validate_workbook_update_profile(bad_key)

    # 3. Disallowed legacy keys
    for legacy_key in ("stock_rule", "order_rule", "requirement_rule"):
        with pytest.raises(ValueError, match="Unsupported key"):
            validate_workbook_update_profile(
                {"parameters": {"workbook_update": {"section_key_column": 2, legacy_key: {}}}}
            )

    # 4. Boolean column or row values
    with pytest.raises(ValueError, match="between 1 and 16384"):
        validate_workbook_update_profile({"parameters": {"workbook_update": {"section_key_column": True}}})
    with pytest.raises(ValueError, match="between 1 and 1048576"):
        validate_workbook_update_profile(
            {"parameters": {"workbook_update": {"section_key_column": 2, "header_row": False}}}
        )

    # 5. Out of range column values (zero, negative, >16384)
    for bad_col in (0, -1, 16385):
        with pytest.raises(ValueError, match="between 1 and 16384"):
            validate_workbook_update_profile({"parameters": {"workbook_update": {"section_key_column": bad_col}}})

    # 6. data_start_row <= header_row
    with pytest.raises(ValueError, match="greater than header_row"):
        validate_workbook_update_profile(
            {"parameters": {"workbook_update": {"section_key_column": 2, "header_row": 3, "data_start_row": 2}}}
        )

    # 7. Unknown key in section_rule
    with pytest.raises(ValueError, match="Unsupported key"):
        validate_workbook_update_profile(
            {
                "parameters": {
                    "workbook_update": {
                        "section_key_column": 2,
                        "section_rules": [{"unknown_rule_key": "val"}],
                    }
                }
            }
        )

    # 8. Unknown key in record_rule
    with pytest.raises(ValueError, match="Unsupported key"):
        validate_workbook_update_profile(
            {
                "parameters": {
                    "workbook_update": {
                        "section_key_column": 2,
                        "record_rules": [{"unknown_rec_key": "val"}],
                    }
                }
            }
        )


def test_converter_semantics():
    # Preexisting localized_number raises ValueError on non-numbers
    with pytest.raises(ValueError):
        _convert_value("invalid_chars", "localized_number")
    with pytest.raises(ValueError):
        _convert_value("not_a_number", "number")

    # Valid localized_number conversions
    assert _convert_value("1 442,0", "localized_number") == 1442
    assert _convert_value("25,5", "localized_number") == 25.5

    # Strict localized number
    assert _convert_value("1 442,0", "strict_localized_number") == 1442
    assert _convert_value("25,5", "strict_localized_float") == 25.5

    # Strict parser rejects malformed dots like 1.2.3
    with pytest.raises(ValueError, match="not a valid strict localized number"):
        _convert_value("1.2.3", "strict_localized_number")

    with pytest.raises(ValueError, match="not a valid strict localized number"):
        _convert_value("1.2.3", "strict_localized_float")


def test_generic_maintenance_domain_pipeline(tmp_path):
    """Verify generic engine on a completely distinct Facility Maintenance domain.

    Layout:
      - Header row: 2
      - Data start row: 4
      - Section key column: 3 (Facility ID)
      - Reference column: 5 (Task ID)
      - Quantity column: 6 (Estimated Hours)
      - Date column: 7 (Due Date, ISO format)
    """
    # 1. Create baseline template workbook
    template_path = tmp_path / "facility_baseline.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "MaintenancePlan"
    # Row 2: Headers
    ws.cell(2, 1, "Facility Name")
    ws.cell(2, 3, "Facility ID")
    ws.cell(2, 5, "Task Reference")
    ws.cell(2, 6, "Hours")
    ws.cell(2, 7, "Due Date")

    # Row 4: Existing row for Facility 'FAC-100' with an existing task and manual hours
    ws.cell(4, 1, "Central Plant")
    ws.cell(4, 3, "FAC-100")
    ws.cell(4, 5, "TSK-001")
    ws.cell(4, 6, 8.0)  # Manual override hours in template
    ws.cell(4, 7, datetime.date(2026, 10, 1))

    # Row 5: Another row in same facility block (anchor)
    ws.cell(5, 1, "Central Plant")
    ws.cell(5, 3, "FAC-100")
    ws.cell(5, 5, "TSK-002")
    ws.cell(5, 6, 4.0)
    ws.cell(5, 7, datetime.date(2026, 10, 5))

    wb.save(template_path)
    wb.close()

    # 2. Define profile
    profile = {
        "id": "facility_maintenance_v1",
        "adapter": "sectioned_record_matrix_v1",
        "parameters": {
            "section_pattern": r"(?m)^Facility:\s*(?P<fac_id>\S+)\s+Name:\s*(?P<name>.*?)$",
            "section_key_group": "fac_id",
            "record_pattern": (
                r"(?m)^\s*(?P<task_id>TSK-\d+)\s+(?P<hours>[\d.,]+)\s+"
                r"(?P<due_date>\d{4}-\d{2}-\d{2})\s*$"
            ),
            "extraction": {
                "candidate_line_pattern": r"^\s*TSK-\d+",
            },
            "row_rules": [
                {
                    "id": "maintenance_task",
                    "kind": "record",
                    "match": {},
                    "columns": {
                        "1": {"field": "name"},
                        "3": {"section_key": True},
                        "5": {"group": "task_id"},
                        "6": {"group": "hours", "value_type": "number"},
                        "7": {"group": "due_date", "value_type": "iso_date"},
                    },
                }
            ],
            "workbook_update": {
                "sheet_name": "MaintenancePlan",
                "header_row": 2,
                "data_start_row": 4,
                "section_key_column": 3,
                "expected_headers": {
                    "3": ["Facility ID"],
                    "5": ["Task Reference"],
                },
                "source_identity_fields": [
                    {"section_key": True},
                    {"group": "task_id"},
                ],
                "record_rules": [
                    {
                        "id": "maintenance_task",
                        "category": "task",
                        "match": {},
                        "reference_spec": {"group": "task_id"},
                        "reference_column": 5,
                        "quantity_spec": {"group": "hours", "value_type": "number"},
                        "fill_blank_quantity_column": 6,
                        "date_spec": {"group": "due_date", "value_type": "iso_date"},
                        "fill_blank_date_column": 7,
                        "date_number_format": "yyyy-mm-dd",
                        "insert_row_values": {
                            "1": {"field": "name"},
                            "3": {"section_key": True},
                            "5": {"group": "task_id"},
                            "6": {"group": "hours", "value_type": "number"},
                            "7": {"group": "due_date", "value_type": "iso_date"},
                        },
                        "matched_status": "MATCHED_TASK",
                        "insert_status": "ADDED_TASK_ROW",
                    }
                ],
            },
        },
    }

    # 3. Simulate PDF layout text
    pdf_text = (
        "Facility: FAC-100 Name: Central Plant\n"
        "TSK-001  12.0  2026-10-01\n"  # Existing in sheet (sheet has 8.0 -> manual preservation)
        "TSK-003   6.0  2026-10-15\n"  # New task -> should be inserted
    )

    parser = SectionedLayoutParser(profile)
    sections = parser.parse_pages([(1, pdf_text)], source_file="facility_inspection.pdf")
    assert len(sections) == 1
    sec = sections[0]
    assert sec.key == "FAC-100"
    assert len(sec.records) == 2

    # 4. Execute updater
    output_path = tmp_path / "facility_output.xlsx"
    updater = SafeWorkbookUpdater(template_path, profile)
    summary = updater.execute(sections, output_path, "MaintenancePlan")

    # Verification:
    # 1 row inserted (TSK-003)
    assert summary["total_rows_inserted"] == 1
    assert summary["status_counts"]["PRESERVED_MANUAL_QUANTITY"] == 1
    assert summary["status_counts"]["ADDED_TASK_ROW"] == 1

    # Inspect generated workbook
    wb_out = openpyxl.load_workbook(output_path)
    ws_out = wb_out["MaintenancePlan"]
    assert ws_out.max_row == 6  # Originally 5 + 1 inserted

    # Row 4 (TSK-001): manual hours 8.0 preserved, NOT overwritten with 12.0
    assert ws_out.cell(4, 5).value == "TSK-001"
    assert ws_out.cell(4, 6).value == 8.0

    # Row 6 (TSK-003 inserted after row 5):
    assert ws_out.cell(6, 3).value == "FAC-100"
    assert ws_out.cell(6, 5).value == "TSK-003"
    assert ws_out.cell(6, 6).value == 6.0
    assert ws_out.cell(6, 7).value == datetime.datetime(2026, 10, 15)
    assert ws_out.cell(6, 7).number_format == "yyyy-mm-dd"

    # 5. Idempotent rerun: executing again on output must insert 0 rows
    rerun_output = tmp_path / "facility_rerun.xlsx"
    rerun_summary = SafeWorkbookUpdater(output_path, profile).execute(sections, rerun_output, "MaintenancePlan")
    assert rerun_summary["total_rows_inserted"] == 0
    assert rerun_summary["status_counts"]["MATCHED_SOURCE_RECORD"] == 1

    wb_out.close()


def test_reject_aliased_paths(tmp_path):
    template = tmp_path / "t.xlsx"
    template.write_bytes(b"template")
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 test")

    profile = {
        "id": "p",
        "adapter": "sectioned_record_matrix_v1",
        "parameters": {
            "section_pattern": r"^Section\s+(?P<id>\S+)",
            "record_pattern": r"^Record\s+(?P<id>\S+)",
            "row_rules": [{"kind": "record", "match": {}}],
            "workbook_update": {"section_key_column": 2},
        },
    }

    # Attempting to output to the same path as template must fail
    with pytest.raises(ValueError, match="aliases input"):
        run_sectioned_workbook_pipeline(
            profile=profile,
            pdf_paths=[pdf],
            template_workbook_path=template,
            output_workbook_path=template,
        )

    # Attempting to output where output workbook aliases reference workbook input
    reference = tmp_path / "ref.xlsx"
    reference.write_bytes(b"reference")
    with pytest.raises(ValueError, match="aliases input"):
        run_sectioned_workbook_pipeline(
            profile=profile,
            pdf_paths=[pdf],
            template_workbook_path=template,
            output_workbook_path=reference,  # Output aliases reference input
            reference_workbook_path=reference,
        )


def test_text_only_profile_and_exact_identity_matching(tmp_path):
    """Verify that a workflow with no date, no quantity and no planning columns succeeds and preserves exact IDs."""
    template_path = tmp_path / "it_assets.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventory"
    ws.cell(1, 1, "Department")
    ws.cell(1, 2, "Asset Tag")
    ws.cell(1, 3, "Model")

    # Existing row with Asset Tag "0100"
    ws.cell(2, 1, "Engineering")
    ws.cell(2, 2, "0100")
    ws.cell(2, 3, "Laptop A")

    wb.save(template_path)
    wb.close()

    # Profile with no planning, no date, no quantity, match_strip_leading_zeros=False
    profile = {
        "id": "it_inventory_v1",
        "adapter": "sectioned_record_matrix_v1",
        "parameters": {
            "section_pattern": r"(?m)^Dept:\s*(?P<dept>\S+)$",
            "section_key_group": "dept",
            "record_pattern": r"(?m)^\s*TAG:\s*(?P<tag>\S+)\s+MODEL:\s*(?P<model>.+?)\s*$",
            "workbook_update": {
                "sheet_name": "Inventory",
                "header_row": 1,
                "data_start_row": 2,
                "section_key_column": 1,
                "expected_headers": {"1": "Department", "2": "Asset Tag", "3": "Model"},
                "source_identity_fields": [{"section_key": True}, {"group": "tag"}],
                "record_rules": [
                    {
                        "id": "asset_tag_rule",
                        "reference_spec": {"group": "tag"},
                        "reference_column": 2,
                        "match_strip_leading_zeros": False,
                        "insert_row_values": {
                            "1": {"section_key": True},
                            "2": {"group": "tag"},
                            "3": {"group": "model"},
                        },
                    }
                ],
            },
        },
    }

    # Tag "100" (distinct from "0100" since match_strip_leading_zeros=False)
    # Tag "0100" (exact match to existing row 2)
    pdf_text = "Dept: Engineering\nTAG: 100 MODEL: Laptop B\nTAG: 0100 MODEL: Laptop A Updated\n"
    parser = SectionedLayoutParser(profile)
    sections = parser.parse_pages([(1, pdf_text)], source_file="assets.pdf")

    output_path = tmp_path / "it_assets_updated.xlsx"
    updater = SafeWorkbookUpdater(template_path, profile)
    summary = updater.execute(sections, output_path, "Inventory")

    # Tag "100" should be inserted as a new row because "0100" != "100"
    assert summary["total_rows_inserted"] == 1

    wb_out = openpyxl.load_workbook(output_path)
    ws_out = wb_out["Inventory"]
    # Row 2 is "0100"
    assert ws_out.cell(2, 2).value == "0100"
    # Row 3 is "100"
    assert ws_out.cell(3, 2).value == "100"
    assert ws_out.cell(3, 3).value == "Laptop B"
    wb_out.close()

    # Rerun on output must result in 0 inserted rows
    rerun_path = tmp_path / "it_assets_rerun.xlsx"
    rerun_summary = SafeWorkbookUpdater(output_path, profile).execute(sections, rerun_path, "Inventory")
    assert rerun_summary["total_rows_inserted"] == 0
    assert not rerun_summary["allowed_changes"]
