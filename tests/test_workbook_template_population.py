"""Empty templates are populated from current sources, without material fixtures."""

import copy
import datetime
import hashlib
from xml.etree import ElementTree
from zipfile import ZIP_DEFLATED, ZipFile

import openpyxl
import pytest
from openpyxl.styles import PatternFill

from shogun.services.sectioned_workbook_pipeline import SectionedLayoutParser
from shogun.services.sectioned_workbook_updater import (
    SafeWorkbookUpdater,
    validate_workbook_update_profile,
)


@pytest.fixture
def population(tmp_path):
    template = tmp_path / "empty.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Schedule"
    sheet.append([
        "Description", "Equipment", "Job", "Hours", "Due date", "Overdue",
        datetime.date(2026, 7, 1), datetime.date(2026, 8, 1), ">= Sep 2026",
    ])
    sheet.cell(3, 2).fill = PatternFill("solid", fgColor="AADDCC")
    sheet.cell(12, 2).fill = PatternFill("solid", fgColor="AADDCC")
    sheet.row_dimensions[3].height = 23
    book.save(template)
    book.close()
    profile = {
        "id": "equipment_schedule",
        "adapter": "sectioned_record_matrix_v1",
        "parameters": {
            "section_pattern": r"(?m)^Equipment: (?P<id>\S+) Size: (?P<size>\d+)$",
            "section_key_group": "id",
            "record_pattern": r"(?m)^(?P<job>JOB-\d+) (?P<hours>\d+) (?P<date>\d{4}-\d{2}-\d{2})$",
            "extraction": {"candidate_line_pattern": r"^JOB-"},
            "row_rules": [{"kind": "record", "columns": {"0": {"group": "job"}}}],
            "workbook_update": {
                "mode": "populate_template",
                "sheet_name": "Schedule",
                "section_key_column": 2,
                "data_start_row": 3,
                "expected_headers": {"2": "Equipment"},
                "planning_start_column": 6,
                "backlog_headers": ["Overdue"],
                "future_header_patterns": [r"^>="],
                "require_planning_months": True,
                "template_section_values": {"1": {"field": "size"}},
                "template_section_sort": [
                    {"field": "size", "value_type": "number"}, {"section_key": True},
                ],
                "source_identity_fields": [{"section_key": True}, {"group": "job"}],
                "record_rules": [{
                    "id": "job",
                    "match": {},
                    "quantity_spec": {"group": "hours", "value_type": "number"},
                    "date_spec": {"group": "date", "value_type": "iso_date"},
                    "planning_month_quantity": True,
                    "insert_row_values": {
                        "2": {"section_key": True},
                        "3": {"group": "job"},
                        "5": {"group": "date", "value_type": "iso_date"},
                    },
                }],
            },
        },
    }
    return template, profile


def execute(population, tmp_path, text, filename="result.xlsx"):
    template, profile = population
    pages = list(enumerate(text.split("\f"), 1))
    sections = SectionedLayoutParser(profile).parse_pages(pages, source_file="current.pdf")
    path = tmp_path / filename
    summary = SafeWorkbookUpdater(template, profile).execute(sections, path)
    return path, summary


def test_populates_current_sections_and_separate_records_preserving_template(population, tmp_path):
    template, _ = population
    before = hashlib.sha256(template.read_bytes()).hexdigest()
    path, summary = execute(population, tmp_path, (
        "Equipment: NEW-40 Size: 400\nJOB-3 4 2026-10-05\n\f"
        "Equipment: NEW-20 Size: 200\nJOB-1 2 2026-06-08\nJOB-2 3 2026-07-13\n"
    ))
    assert summary["mode"] == "populate_template"
    assert summary["status_counts"]["CREATED_SECTION"] == 2
    assert summary["normalized_record_count"] == summary["accounted_record_count"] == 3
    assert summary["total_rows_inserted"] == 5
    assert "SECTION_NOT_FOUND" not in summary["status_counts"]
    book = openpyxl.load_workbook(path)
    sheet = book["Schedule"]
    assert [sheet.cell(row, 2).value for row in range(3, 8)] == ["NEW-20"] * 3 + ["NEW-40"] * 2
    assert sheet["F4"].value == 2
    assert sheet["G5"].value == 3
    assert sheet["I7"].value == 4
    assert sheet["E7"].value == datetime.datetime(2026, 10, 5)
    assert sheet["B3"].fill.fgColor.rgb == "00AADDCC"
    assert sheet.row_dimensions[3].height == 23
    assert sheet["F1"].value == "Overdue" and sheet["I1"].value == ">= Sep 2026"
    book.close()
    assert hashlib.sha256(template.read_bytes()).hexdigest() == before


def test_new_materials_and_new_months_do_not_require_profile_changes(population, tmp_path):
    template, _ = population
    book = openpyxl.load_workbook(template)
    sheet = book["Schedule"]
    sheet["G1"] = datetime.date(2028, 1, 1)
    sheet["H1"] = datetime.date(2028, 2, 1)
    sheet["I1"] = ">= Mar 2028"
    book.save(template)
    book.close()
    path, summary = execute(population, tmp_path, (
        "Equipment: UNSEEN-900 Size: 900\nJOB-99 17 2028-02-07\n\f"
        "Equipment: UNSEEN-100 Size: 100\nJOB-98 8 2028-04-03\n"
    ))
    assert summary["total_rows_inserted"] == 4
    book = openpyxl.load_workbook(path)
    sheet = book["Schedule"]
    assert sheet["B3"].value == "UNSEEN-100" and sheet["I4"].value == 8
    assert sheet["B5"].value == "UNSEEN-900" and sheet["H6"].value == 17
    book.close()


def test_population_refuses_populated_input_instead_of_duplicating_or_overwriting(population, tmp_path):
    template, _ = population
    book = openpyxl.load_workbook(template)
    book["Schedule"]["A8"] = "Planner note that must survive"
    book.save(template)
    book.close()
    before = template.read_bytes()
    with pytest.raises(ValueError, match="requires an empty data area"):
        execute(population, tmp_path, "Equipment: NEW-1 Size: 100\nJOB-1 4 2026-07-06\n")
    assert not (tmp_path / "result.xlsx").exists()
    assert template.read_bytes() == before


def test_template_with_only_headers_and_no_formatted_body(population, tmp_path):
    template, _ = population
    book = openpyxl.load_workbook(template)
    book["Schedule"].delete_rows(2, book["Schedule"].max_row)
    book.save(template)
    book.close()
    path, summary = execute(population, tmp_path, "Equipment: NEW-1 Size: 100\nJOB-1 4 2026-07-06\n")
    assert summary["total_rows_inserted"] == 2
    book = openpyxl.load_workbook(path)
    assert book["Schedule"]["B3"].value == "NEW-1"
    assert book["Schedule"]["G4"].value == 4
    book.close()


def test_default_update_mode_still_requires_existing_sections(population, tmp_path):
    _, profile = population
    del profile["parameters"]["workbook_update"]["mode"]
    _, summary = execute(population, tmp_path, "Equipment: NEW-1 Size: 100\nJOB-1 4 2026-07-06\n")
    assert summary["total_rows_inserted"] == 0
    assert summary["status_counts"]["SECTION_NOT_FOUND"] == 2


def test_unknown_planning_header_still_fails(population, tmp_path):
    template, _ = population
    book = openpyxl.load_workbook(template)
    book["Schedule"]["J1"] = "Unmapped measure"
    book.save(template)
    book.close()
    with pytest.raises(ValueError, match="Unsupported planning header"):
        execute(population, tmp_path, "Equipment: NEW-1 Size: 100\nJOB-1 4 2026-07-06\n")


def test_equivalent_style_table_entries_and_blank_values_round_trip(population, tmp_path):
    template, profile = population
    # Real Excel files may contain duplicate alignment entries with different IDs.
    # A save deduplicates these; that must not count as changing cell formatting.
    with ZipFile(template) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    styles = ElementTree.fromstring(files["xl/styles.xml"])
    alignments = styles.find("s:cellXfs", ns)
    original = alignments[1]
    original.append(ElementTree.Element("{" + ns["s"] + "}alignment", horizontal="left"))
    duplicate = copy.deepcopy(original)
    alignments.append(duplicate)
    alignments.set("count", str(len(alignments)))
    files["xl/styles.xml"] = ElementTree.tostring(styles)
    sheet = ElementTree.fromstring(files["xl/worksheets/sheet1.xml"])
    sheet.find(".//s:c[@r='B3']", ns).set("s", str(len(alignments) - 1))
    files["xl/worksheets/sheet1.xml"] = ElementTree.tostring(sheet)
    with ZipFile(template, "w", ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    profile["parameters"]["workbook_update"]["template_section_values"]["4"] = {"literal": ""}
    path, summary = execute(population, tmp_path, "Equipment: FRESH-1 Size: 100\nJOB-1 4 2026-07-06\n")
    assert summary["total_rows_inserted"] == 2
    book = openpyxl.load_workbook(path)
    assert book["Schedule"]["B3"].alignment.horizontal == "left"
    assert book["Schedule"]["D3"].value is None
    book.close()


@pytest.mark.parametrize("change", [
    {"mode": []}, {"backlog_headers": "Overdue"}, {"future_header_patterns": [False]},
    {"template_section_values": {"0": {"literal": "bad"}}}, {"template_section_sort": [{}] * 9},
])
def test_population_configuration_is_validated(population, change):
    _, profile = population
    modified = copy.deepcopy(profile)
    modified["parameters"]["workbook_update"].update(change)
    with pytest.raises(ValueError):
        validate_workbook_update_profile(modified)
