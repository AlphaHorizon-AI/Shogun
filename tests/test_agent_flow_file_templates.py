import uuid
from copy import copy
from datetime import datetime
from types import SimpleNamespace

import openpyxl
import pytest
from docx import Document

from shogun.config import settings
from shogun.engine import flow_engine
from shogun.services.file_template import (
    TEMPLATE_MARKER,
    extract_file_template,
    format_template_guidance,
    parse_excel_rows,
    render_excel_template,
    render_word_template,
)


def test_excel_json_object_rows_follow_template_column_order():
    payload = """```json
[{"Amount": 20, "Item": "140006", "2026-07-01": 10},
 {"Item": "140023", "2026-07-01": 5, "Amount": 12}]
```"""

    rows = parse_excel_rows(
        payload,
        template_headers=[None, "Item", "Amount", datetime(2026, 7, 1)],
    )

    assert rows == [[None, "140006", 20, 10], [None, "140023", 12, 5]]


def test_excel_chunked_and_individually_serialized_json_rows_are_decoded():
    payload = """[Output from 'Extract & Map Data']:
```json
["{\\"Item\\":\\"A\\",\\"Amount\\":1}"]
```
```json
[{"Item":"B","Amount":2}]
```"""

    rows = parse_excel_rows(payload, template_headers=["Item", "Amount"])

    assert rows == [["A", 1], ["B", 2]]


def test_excel_incomplete_structured_json_is_rejected():
    with pytest.raises(ValueError, match="incomplete or truncated"):
        parse_excel_rows('```json\n[["A", "B"]')


def test_excel_manifest_and_adaptive_render_ignore_formatting_only_rows(tmp_path):
    source = tmp_path / "source.xlsx"
    output = tmp_path / "Output" / "result.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Plan"
    ws.append(["Description", "Item", "Quantity"])
    ws.append([None, "Nr.", "Stk."])
    ws.append(["Existing", "100", 1])
    ws["A100"].fill = openpyxl.styles.PatternFill(fill_type="solid", fgColor="FFFF00")
    wb.save(source)
    wb.close()

    payload = extract_file_template("source.xlsx", tmp_path)
    sheet = payload["manifest"]["sheets"][0]
    assert sheet["logical_range"] == "A1:C3"
    assert sheet["logical_columns"] == 3
    assert sheet["suggested_append_cell"] == "A4"

    changed = render_excel_template(
        source,
        output,
        '[["Generated", "200", 2]]',
        "append",
        "Plan",
        render_mode="adaptive",
    )
    assert changed == 3
    rendered = openpyxl.load_workbook(output)
    try:
        assert rendered["Plan"]["A3"].value == "Existing"
        assert rendered["Plan"]["A4"].value == "Generated"
        assert rendered["Plan"]["C4"].value == 2
        assert rendered["Plan"]["A100"].value is None
    finally:
        rendered.close()


def test_excel_template_matrix_width_is_validated():
    with pytest.raises(ValueError, match="exactly 3 values"):
        parse_excel_rows('[["A", "B"]]', template_headers=["One", "Two", "Three"])


def test_word_template_structure_and_one_shot_are_explicit(tmp_path):
    template = tmp_path / "report.docx"
    doc = Document()
    doc.add_heading("Quarterly Report", level=1)
    doc.add_paragraph("Customer: {{customer}}")
    doc.add_paragraph("Example conclusion")
    doc.save(template)

    structure = extract_file_template("report.docx", tmp_path, "structure_only")
    assert structure[TEMPLATE_MARKER] is True
    assert structure["format"] == "docx"
    assert "Quarterly Report" in structure["contract"]
    assert "customer" in structure["contract"]
    assert structure["example"] == ""

    one_shot = extract_file_template("report.docx", tmp_path, "one_shot", "replace")
    guidance = format_template_guidance(one_shot)
    assert "[POPULATED ONE-SHOT EXAMPLE]" in guidance
    assert "Example conclusion" in guidance
    assert "example records are non-authoritative" in guidance
    assert "reference-only output contract" in guidance
    assert "sole source of business records" in guidance


def test_word_template_render_creates_copy_and_replaces_json_placeholders(tmp_path):
    source = tmp_path / "source.docx"
    output = tmp_path / "Output" / "result.docx"
    doc = Document()
    doc.add_heading("Client Brief", level=1)
    doc.add_paragraph("Client: {{client}}")
    doc.add_paragraph("Summary: {{summary}}")
    doc.save(source)

    changed = render_word_template(
        source,
        output,
        '[Output from \'Samurai\']:\n{"client":"Acme","summary":"Ready"}',
        "replace",
    )

    assert changed == 2
    assert "{{client}}" in "\n".join(p.text for p in Document(source).paragraphs)
    rendered = "\n".join(p.text for p in Document(output).paragraphs)
    assert "Client: Acme" in rendered
    assert "Summary: Ready" in rendered


def test_word_adaptive_render_populates_repeating_table_rows(tmp_path):
    source = tmp_path / "source.docx"
    output = tmp_path / "Output" / "result.docx"
    document = Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Item"
    table.cell(0, 1).text = "Quantity"
    table.cell(1, 0).text = "Example"
    table.cell(1, 1).text = "1"
    document.save(source)

    changed = render_word_template(
        source,
        output,
        '[["A", 2], ["B", 3]]',
        "replace",
        render_mode="adaptive",
    )

    rendered = Document(output)
    assert changed == 4
    assert [[cell.text for cell in row.cells] for row in rendered.tables[0].rows] == [
        ["Item", "Quantity"],
        ["A", "2"],
        ["B", "3"],
    ]


def test_excel_one_shot_replace_preserves_template_and_styles(tmp_path):
    source = tmp_path / "source.xlsx"
    output = tmp_path / "Output" / "result.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"
    ws.append(["Customer", "Amount"])
    ws.append(["Example Co", 100])
    sample_font = copy(ws["A1"].font)
    sample_font.bold = True
    ws["A2"].font = sample_font
    wb.save(source)
    wb.close()

    payload = extract_file_template("source.xlsx", tmp_path, "one_shot", "replace")
    assert "Example Co" in payload["example"]
    assert "Customer | Amount" in payload["contract"]

    changed = render_excel_template(
        source,
        output,
        "| Customer | Amount |\n| --- | --- |\n| New Co | 250 |",
        "replace",
        "Orders",
    )
    assert changed == 2

    original = openpyxl.load_workbook(source)
    rendered = openpyxl.load_workbook(output)
    try:
        assert original["Orders"]["A2"].value == "Example Co"
        assert rendered["Orders"]["A2"].value == "New Co"
        assert rendered["Orders"]["B2"].value == "250"
        assert rendered["Orders"]["A2"].font.bold is True
    finally:
        original.close()
        rendered.close()


def test_excel_one_shot_replace_overrides_adaptive_placement(tmp_path):
    source = tmp_path / "source.xlsx"
    output = tmp_path / "Output" / "result.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"
    ws.append(["Item", "Quantity"])
    ws.append(["EXAMPLE-A", 100])
    ws.append(["EXAMPLE-B", 200])
    wb.save(source)
    wb.close()

    changed = render_excel_template(
        source,
        output,
        '[["SOURCE-A", 12]]',
        "replace",
        "Orders",
        render_mode="adaptive",
    )

    assert changed == 2
    rendered = openpyxl.load_workbook(output)
    try:
        assert rendered["Orders"]["A2"].value == "SOURCE-A"
        assert rendered["Orders"]["B2"].value == 12
        assert rendered["Orders"]["A3"].value is None
        assert rendered["Orders"]["B3"].value is None
    finally:
        rendered.close()


def test_excel_anchored_replace_clears_remaining_example_rows(tmp_path):
    source = tmp_path / "source.xlsx"
    output = tmp_path / "Output" / "result.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Orders"
    ws.append(["Report title", None])
    ws.append(["Item", "Quantity"])
    ws.append([None, None])
    ws.append(["EXAMPLE-A", 100])
    ws.append(["EXAMPLE-B", 200])
    wb.save(source)
    wb.close()

    changed = render_excel_template(
        source,
        output,
        '[["SOURCE-A", 12]]',
        "replace",
        "Orders",
        start_cell="A4",
        render_mode="adaptive",
    )

    assert changed == 2
    rendered = openpyxl.load_workbook(output)
    try:
        assert rendered["Orders"]["A4"].value == "SOURCE-A"
        assert rendered["Orders"]["B4"].value == 12
        assert rendered["Orders"]["A5"].value is None
        assert rendered["Orders"]["B5"].value is None
    finally:
        rendered.close()


def test_template_ancestry_reaches_downstream_create_node():
    payload = {TEMPLATE_MARKER: True, "template_path": "Templates/report.docx"}
    predecessors = {"samurai": ["template"], "files": ["samurai"]}
    outputs = {"template": payload, "samurai": "generated content"}

    assert flow_engine._collect_upstream_file_templates("files", predecessors, outputs) == [payload]


def test_input_fan_out_triggers_template_and_parallel_branch_together():
    input_id = uuid.uuid4()
    template_id = uuid.uuid4()
    parallel_id = uuid.uuid4()
    samurai_id = uuid.uuid4()
    nodes = [
        SimpleNamespace(id=input_id),
        SimpleNamespace(id=template_id),
        SimpleNamespace(id=parallel_id),
        SimpleNamespace(id=samurai_id),
    ]
    edges = [
        SimpleNamespace(source_node_id=input_id, target_node_id=template_id),
        SimpleNamespace(source_node_id=input_id, target_node_id=parallel_id),
        SimpleNamespace(source_node_id=template_id, target_node_id=samurai_id),
    ]

    layers = flow_engine._topological_sort(nodes, edges)

    assert layers[0] == [str(input_id)]
    assert set(layers[1]) == {str(template_id), str(parallel_id)}
    assert layers[2] == [str(samurai_id)]


@pytest.mark.asyncio
async def test_word_create_uses_upstream_template_and_never_changes_source(tmp_path, monkeypatch):
    from shogun.office import config as office_config

    template = tmp_path / "Templates" / "brief.docx"
    template.parent.mkdir(parents=True)
    doc = Document()
    doc.add_paragraph("Customer: {{customer}}")
    doc.save(template)
    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    monkeypatch.setattr(office_config, "load_office_config", lambda: SimpleNamespace(enabled=True))

    result = await flow_engine._exec_office(
        {"action": "word_create", "output_path": "Output", "output_filename": "brief.docx"},
        '{"customer":"Acme"}',
        run_id=uuid.uuid4(),
        trigger_type="manual",
        template_inputs=[
            {
                TEMPLATE_MARKER: True,
                "template_path": "Templates/brief.docx",
                "format": "docx",
                "example_handling": "replace",
            }
        ],
    )

    assert "Word document created" in result
    assert "{{customer}}" in Document(template).paragraphs[0].text
    assert "Customer: Acme" in Document(tmp_path / "Output" / "brief.docx").paragraphs[0].text


def test_template_path_must_stay_in_workspace(tmp_path):
    outside = tmp_path.parent / "outside.docx"
    Document().save(outside)
    with pytest.raises(ValueError, match="workspace"):
        extract_file_template(str(outside), tmp_path)
