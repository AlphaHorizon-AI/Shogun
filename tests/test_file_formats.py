from __future__ import annotations

import json
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.config import settings
from shogun.db.models.file_artifact import FileArtifact
from shogun.services.event_logger import EventLogger
from shogun.services.file_formats import (
    AdapterRegistry,
    AdapterSpec,
    BaseAdapter,
    FileFormatError,
    FileFormatService,
    Inspection,
    registry,
)
from shogun.services.native_skills import NATIVE_TOOLS
from shogun.services.posture_guard import filter_tools_by_posture
from shogun.services.tool_gate import get_tool_category, get_tool_risk


@pytest.fixture(autouse=True)
def no_audit(monkeypatch):
    monkeypatch.setattr(EventLogger, "emit", AsyncMock(return_value="evt_file_test"))


def service(tmp_path: Path) -> FileFormatService:
    return FileFormatService(allowed_roots=[tmp_path])


@pytest.mark.asyncio
async def test_content_detection_overrides_wrong_json_extension(tmp_path):
    path = tmp_path / "payload.txt"
    path.write_text('{"customers": [{"name": "A"}]}', encoding="utf-8")

    result = await service(tmp_path).detect(path=str(path))

    assert result["detected_format"] == "json"
    assert result["method"] == "content_sniffing"


@pytest.mark.asyncio
async def test_csv_delimiter_schema_profile_and_query(tmp_path):
    path = tmp_path / "orders.csv"
    path.write_text("id;amount;email\n1;12.5;a@example.com\n2;;b@example.com\n2;;b@example.com\n", encoding="utf-8")
    svc = service(tmp_path)

    result = await svc.inspect(path=str(path))
    queried = await svc.query("id=2", path=str(path))

    assert result["format_id"] == "csv"
    assert result["data"]["delimiter"] == ";"
    assert result["data"]["rows"] == 3
    assert result["data"]["missing_values"]["amount"] == 2
    assert result["data"]["duplicate_rows"] == 1
    assert result["schema"]["columns"]["id"] == "integer"
    assert len(queried["data"]) == 2


@pytest.mark.asyncio
async def test_json_validation_and_simple_json_path(tmp_path):
    path = tmp_path / "orders.json"
    path.write_text(json.dumps({"orders": [{"total": 12}, {"total": 25}]}), encoding="utf-8")
    svc = service(tmp_path)

    result = await svc.query("$.orders[*].total", path=str(path))

    assert result["data"] == [12, 25]
    invalid = tmp_path / "broken.json"
    invalid.write_text('{"x":', encoding="utf-8")
    validated = await svc.validate(path=str(invalid))
    assert validated["valid"] is False
    assert validated["error_type"] == "parse_error"


@pytest.mark.asyncio
async def test_jsonl_reports_invalid_lines_and_infers_schema(tmp_path):
    path = tmp_path / "events.ndjson"
    path.write_text('{"level":"info","id":1}\nnot-json\n{"level":"error","id":2}\n', encoding="utf-8")

    result = await service(tmp_path).inspect(path=str(path))

    assert result["data"]["valid_records"] == 2
    assert result["data"]["invalid_records"] == 1
    assert result["schema"]["fields"]["id"] == ["integer"]


@pytest.mark.asyncio
async def test_xml_dtd_and_external_entities_are_blocked(tmp_path):
    path = tmp_path / "unsafe.xml"
    path.write_text('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><foo>&xxe;</foo>', encoding="utf-8")

    with pytest.raises(FileFormatError, match="blocked") as caught:
        await service(tmp_path).inspect(path=str(path))

    assert caught.value.error_type == "unsafe_xml"


@pytest.mark.asyncio
async def test_yaml_safe_loader_rejects_python_constructor(tmp_path):
    pytest.importorskip("yaml")
    path = tmp_path / "unsafe.yaml"
    path.write_text("!!python/object/apply:os.system ['echo unsafe']", encoding="utf-8")

    result = await service(tmp_path).validate(path=str(path))

    assert result["valid"] is False
    assert result["error_type"] == "parse_error"


@pytest.mark.asyncio
async def test_config_markdown_html_log_and_code_adapters(tmp_path):
    fixtures = {
        "app.toml": "[server]\nport = 8000\n",
        "README.md": "# Install\nText\n## Usage\n[Docs](https://example.test)\n",
        "page.html": (
            "<html><head><title>Hello</title><script>secret()</script></head>"
            '<body><a href="/x">Link</a>Visible</body></html>'
        ),
        "app.log": "INFO start\nERROR failed\nERROR failed\nWARN retry\n",
        "app.py": "import os\n\ndef run():\n    return True\n",
    }
    results = {}
    for filename, content in fixtures.items():
        path = tmp_path / filename
        path.write_text(content, encoding="utf-8")
        results[filename] = await service(tmp_path).inspect(path=str(path))

    assert results["app.toml"]["data"]["sections"] == ["server"]
    assert [item["title"] for item in results["README.md"]["data"]["headings"]] == ["Install", "Usage"]
    assert "Visible" in results["page.html"]["preview"] and "secret()" not in results["page.html"]["preview"]
    assert results["app.log"]["data"]["levels"]["ERROR"] == 2
    assert results["app.py"]["data"]["symbols"][0]["name"] == "run"
    assert any("not executed" in warning for warning in results["app.py"]["warnings"])


@pytest.mark.asyncio
async def test_secret_masking_applies_to_previews(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("# Config\napi_key=super-secret-value\n", encoding="utf-8")

    result = await service(tmp_path).inspect(path=str(path))

    assert "super-secret-value" not in result["preview"]
    assert "[REDACTED]" in result["preview"]
    assert any("Masked" in warning for warning in result["warnings"])

    structured = tmp_path / "secrets.json"
    structured.write_text('{"username":"michael","api_key":"do-not-show-this-value"}', encoding="utf-8")
    structured_result = await service(tmp_path).inspect(path=str(structured))
    assert structured_result["preview"]["api_key"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_csv_export_sanitizes_formula_injection_and_versions_outputs(tmp_path, monkeypatch):
    path = tmp_path / "input.json"
    path.write_text('[{"name":"=CMD()","value":1}]', encoding="utf-8")
    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    svc = service(tmp_path)

    first = await svc.transform("csv", "safe.csv", {"sanitize_formulas": True}, path=str(path))
    second = await svc.transform("csv", "safe.csv", {"sanitize_formulas": True}, path=str(path))

    first_path = Path(first["artifacts"][0]["path"])
    second_path = Path(second["artifacts"][0]["path"])
    assert "'=CMD()" in first_path.read_text(encoding="utf-8")
    assert first_path != second_path
    assert path.read_text(encoding="utf-8").startswith("[")


@pytest.mark.asyncio
async def test_inspection_registers_file_id_and_supports_later_lookup(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(FileArtifact.__table__.create)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    path = tmp_path / "registered.json"
    path.write_text('{"ok":true}', encoding="utf-8")

    async with sessions() as session:
        svc = FileFormatService(session, [tmp_path])
        inspected = await svc.inspect(path=str(path), source="test")
        await session.commit()
        fetched = await svc.get_artifact(inspected["file_id"])
        queried = await svc.query("$.ok", file_id=inspected["file_id"])

    assert fetched["format_id"] == "json"
    assert fetched["hash_sha256"] == inspected["hash_sha256"]
    assert queried["data"] is True
    await engine.dispose()


@pytest.mark.asyncio
async def test_bounded_file_read_returns_content_and_truncates(tmp_path):
    path = tmp_path / "chat-notes.txt"
    path.write_text("important note\n" * 500, encoding="utf-8")

    result = await service(tmp_path).read(path=str(path), max_chars=1000)

    assert result["operation"] == "read"
    assert "important note" in result["content"]
    assert len(result["content"]) == 1000
    assert result["truncated"] is True


@pytest.mark.asyncio
async def test_ooxml_files_are_detected_as_office_not_generic_zip(tmp_path):
    path = tmp_path / "brief.docx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
        archive.writestr("word/document.xml", "<document />")

    result = await service(tmp_path).detect(path=str(path))

    assert result["detected_format"] == "office"


@pytest.mark.asyncio
async def test_chat_reader_extracts_word_document_text(tmp_path):
    docx = pytest.importorskip("docx")
    path = tmp_path / "brief.docx"
    document = docx.Document()
    document.add_heading("Launch Plan", level=1)
    document.add_paragraph("Ship the governed file reader.")
    document.save(path)

    result = await service(tmp_path).read(path=str(path))

    assert result["format_id"] == "office"
    assert "Launch Plan" in result["content"]
    assert "governed file reader" in result["content"]


@pytest.mark.asyncio
async def test_chat_reader_extracts_excel_sheet_data_offline(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    path = tmp_path / "sales.xlsx"
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Quarterly Sales"
    sheet.append(["Region", "Revenue"])
    sheet.append(["North", 125000])
    sheet.append(["South", 98000])
    workbook.save(path)
    workbook.close()

    result = await service(tmp_path).read(path=str(path))

    assert result["format_id"] == "office"
    assert "Quarterly Sales" in result["metadata"]["sheets"]
    assert result["metadata"]["selected_sheet"] == "Quarterly Sales"
    assert "North" in result["content"]
    assert "125000" in result["content"]


@pytest.mark.asyncio
async def test_zip_inspection_and_zip_slip_blocking(tmp_path, monkeypatch):
    path = tmp_path / "package.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("safe/data.csv", "id\n1\n")
        archive.writestr("../escape.txt", "blocked")
    svc = service(tmp_path)

    inspection = await svc.inspect(path=str(path))
    assert inspection["data"]["unsafe_entries"] == 1

    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    with pytest.raises(FileFormatError) as approval:
        await svc.extract_archive(["safe/data.csv"], path=str(path))
    assert approval.value.error_type == "approval_required"
    with pytest.raises(FileFormatError) as caught:
        await svc.extract_archive(["../escape.txt"], approved=True, path=str(path))
    assert caught.value.error_type == "unsafe_archive"


@pytest.mark.asyncio
async def test_safe_selected_zip_extraction_and_no_overwrite(tmp_path, monkeypatch):
    path = tmp_path / "package.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("safe/data.csv", "id\n1\n")
    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    svc = service(tmp_path)

    result = await svc.extract_archive(["safe/data.csv"], approved=True, path=str(path))

    extracted = Path(result["artifacts"][0]["path"])
    assert extracted.read_text(encoding="utf-8") == "id\n1\n"
    with pytest.raises(FileFormatError) as caught:
        await svc.extract_archive(["safe/data.csv"], approved=True, path=str(path))
    assert caught.value.error_type == "overwrite_blocked"


@pytest.mark.asyncio
async def test_unknown_binary_fallback_is_honest(tmp_path):
    path = tmp_path / "sample.proprietary"
    path.write_bytes(b"\x00\x01\x02vendor-data")

    result = await service(tmp_path).inspect(path=str(path))

    assert result["format_id"] == "unknown"
    assert result["data"]["binary"] is True
    assert any("not natively supported" in warning for warning in result["warnings"])


@pytest.mark.asyncio
async def test_outside_workspace_and_large_files_are_blocked(tmp_path, monkeypatch):
    inside = tmp_path / "large.txt"
    inside.write_text("1234567890", encoding="utf-8")
    monkeypatch.setattr(settings, "file_max_parse_bytes", 5)
    with pytest.raises(FileFormatError) as caught:
        await service(tmp_path).inspect(path=str(inside))
    assert caught.value.error_type == "file_too_large"

    outside = tmp_path.parent / "outside-order19.txt"
    outside.write_text("outside", encoding="utf-8")
    try:
        with pytest.raises(FileFormatError) as caught:
            await service(tmp_path).inspect(path=str(outside))
        assert caught.value.error_type == "path_outside_workspace"
    finally:
        outside.unlink(missing_ok=True)


def test_registry_tools_toolgate_and_posture_are_integrated():
    format_ids = {item["format_id"] for item in registry.formats()}
    assert {
        "csv",
        "json",
        "jsonl",
        "xml",
        "yaml",
        "config",
        "markdown",
        "html",
        "log",
        "code",
        "zip",
        "unknown",
    } <= format_ids

    file_tools = [tool for tool in NATIVE_TOOLS if tool["function"]["name"].startswith("file_")]
    names = {tool["function"]["name"] for tool in file_tools}
    assert {
        "file_detect_type",
        "file_inspect",
        "file_preview",
        "file_schema",
        "file_query",
        "file_extract",
        "file_compare",
        "file_validate",
        "file_transform",
        "file_export",
        "file_archive_extract_selected",
        "file_index_profile",
        "file_index",
        "file_list_formats",
    } <= names
    assert get_tool_category("file_inspect") == "files"
    assert get_tool_risk("file_archive_extract_selected").value == "high"

    allowed, denied = filter_tools_by_posture(file_tools, {"filesystem_mode": "allowlist"})
    assert "file_inspect" in {tool["function"]["name"] for tool in allowed}
    assert {"file_transform", "file_export", "file_archive_extract_selected"} <= set(denied)


def test_proprietary_adapter_hook_requires_no_generic_tool_changes(tmp_path):
    class VendorAdapter(BaseAdapter):
        spec = AdapterSpec("vendor", "Vendor Export", (".vendor",), ("application/x-vendor",), ("inspect",))

        def inspect(self, path: Path, max_rows: int) -> Inspection:
            return Inspection("Vendor adapter parsed the file.", {"vendor": True})

    custom = AdapterRegistry()
    custom.register(VendorAdapter())
    path = tmp_path / "data.vendor"
    path.write_text("vendor", encoding="utf-8")

    assert custom.detect(path).detected_format == "vendor"
    assert custom.get("vendor").inspect(path, 10).data == {"vendor": True}
