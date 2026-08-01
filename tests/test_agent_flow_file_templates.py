import uuid
from copy import copy
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
    render_excel_template,
    render_word_template,
)


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
    assert "not as factual input" in guidance


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


def test_template_ancestry_reaches_downstream_create_node():
    payload = {TEMPLATE_MARKER: True, "template_path": "Templates/report.docx"}
    predecessors = {"samurai": ["template"], "files": ["samurai"]}
    outputs = {"template": payload, "samurai": "generated content"}

    assert flow_engine._collect_upstream_file_templates("files", predecessors, outputs) == [payload]


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
