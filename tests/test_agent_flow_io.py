import uuid
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import UploadFile

from shogun.config import settings
from shogun.engine import flow_engine


@pytest.mark.asyncio
async def test_agent_flow_upload_uses_configured_upload_directory(tmp_path, monkeypatch):
    from shogun.api.agent_flow import upload_flow_document

    flow_id = uuid.uuid4()
    upload_root = tmp_path / "uploads"
    monkeypatch.setattr(settings, "uploads_path", upload_root)

    class FakeFlowService:
        async def get_by_id(self, requested_flow_id):
            assert requested_flow_id == flow_id
            return object()

    response = await upload_flow_document(
        flow_id,
        UploadFile(filename="Mapla 21.07.2026.pdf", file=BytesIO(b"%PDF-1.4 test")),
        FakeFlowService(),
    )

    expected = upload_root / "agent_flows" / str(flow_id) / "Mapla 21.07.2026.pdf"
    assert expected.read_bytes() == b"%PDF-1.4 test"
    assert response.data["path"] == str(expected)


@pytest.mark.asyncio
async def test_document_input_requires_an_uploaded_file():
    with pytest.raises(ValueError, match="No document was uploaded"):
        await flow_engine._exec_input({"input_type": "document"}, "")


@pytest.mark.asyncio
async def test_document_input_reports_incomplete_upload():
    with pytest.raises(ValueError, match="did not complete successfully"):
        await flow_engine._exec_input(
            {
                "input_type": "document",
                "uploaded_file": {
                    "filename": "Mapla 21.07.2026.pdf",
                    "size": 1234,
                    "path": "",
                    "error": "Upload failed",
                },
            },
            "",
        )


@pytest.mark.asyncio
async def test_document_input_uses_bounded_format_reader(tmp_path):
    document = tmp_path / "input.txt"
    document.write_text("mapped source content", encoding="utf-8")

    result = await flow_engine._exec_input(
        {
            "input_type": "document",
            "uploaded_file": {"path": str(document), "filename": document.name},
        },
        "",
    )

    assert "[Document: input.txt]" in result
    assert "mapped source content" in result


@pytest.mark.asyncio
async def test_agent_flow_document_is_not_clipped_at_legacy_chat_limit(tmp_path):
    content = "row-data\n" * 20_000
    document = tmp_path / "large-input.txt"
    document.write_text(content, encoding="utf-8")

    result = await flow_engine._exec_input(
        {
            "input_type": "document",
            "uploaded_file": {"path": str(document), "filename": document.name},
        },
        "",
    )

    assert len(content) > 100_000
    assert content in result.replace("\r\n", "\n")


@pytest.mark.asyncio
async def test_document_input_reads_workspace_file(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    document = workspace / "Input" / "source.txt"
    document.parent.mkdir(parents=True)
    document.write_text("workspace source content", encoding="utf-8")
    monkeypatch.setattr(settings, "workspace_path", workspace)

    result = await flow_engine._exec_input(
        {
            "input_type": "document",
            "document_source": "workspace",
            "workspace_path": "Input/source.txt",
        },
        "",
    )

    assert "[Document: source.txt]" in result
    assert "workspace source content" in result


@pytest.mark.asyncio
async def test_document_input_blocks_workspace_escape(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("must not be read", encoding="utf-8")
    monkeypatch.setattr(settings, "workspace_path", workspace)

    with pytest.raises(ValueError, match="must remain inside the configured workspace"):
        await flow_engine._exec_input(
            {
                "input_type": "document",
                "document_source": "workspace",
                "workspace_path": str(outside),
            },
            "",
        )


@pytest.mark.asyncio
async def test_document_input_reads_bound_chat_attachment(monkeypatch):
    from shogun.services import file_formats

    file_id = uuid.uuid4()

    class FakeSessionContext:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    class FakeFileFormatService:
        def __init__(self, session=None, allowed_roots=None):
            assert session is not None

        async def read(self, *, file_id, max_chars):
            assert max_chars == settings.agent_flow_document_max_chars
            return {"filename": "attached.pdf", "content": "attachment source content"}

    monkeypatch.setattr(flow_engine, "async_session_factory", lambda: FakeSessionContext())
    monkeypatch.setattr(file_formats, "FileFormatService", FakeFileFormatService)

    result = await flow_engine._exec_input(
        {
            "input_type": "document",
            "document_source": "attachment",
            "attachment_file_id": str(file_id),
        },
        "",
    )

    assert "[Document: attached.pdf]" in result
    assert "attachment source content" in result


@pytest.mark.asyncio
async def test_samurai_node_receives_complete_predecessor_document(monkeypatch):
    predecessor = "page data\n" * 10_000
    captured: dict[str, str] = {}

    async def update_state(*_args, **_kwargs):
        return None

    async def execute_samurai(_config, context, _governance, **_kwargs):
        captured["context"] = context
        return "done"

    monkeypatch.setattr(flow_engine, "_update_node_state", update_state)
    monkeypatch.setattr(flow_engine, "_exec_samurai", execute_samurai)
    monkeypatch.setattr(flow_engine, "_finalize_node_skills", update_state)
    node = SimpleNamespace(
        id=uuid.uuid4(),
        flow_id=uuid.uuid4(),
        node_type="samurai",
        label="Extract",
        config={"task_description": "Extract all rows"},
    )
    predecessor_id = str(uuid.uuid4())
    predecessor_node = SimpleNamespace(label="Input PDF")

    result = await flow_engine._execute_single_node(
        uuid.uuid4(),
        node,
        {predecessor_id: predecessor},
        {predecessor_id: predecessor_node},
    )

    assert result == "done"
    assert predecessor in captured["context"]
    assert "[...truncated...]" not in captured["context"]


def test_legacy_failure_sentinels_are_real_failures():
    with pytest.raises(RuntimeError, match="Office App Mode is disabled"):
        flow_engine._validated_node_result("[BLOCKED] Office App Mode is disabled")
    with pytest.raises(RuntimeError, match="Permission denied"):
        flow_engine._validated_node_result("[ERROR] Permission denied")


@pytest.mark.asyncio
async def test_pdf_read_uses_workspace_file_without_office_app_mode(tmp_path, monkeypatch):
    from shogun.office import config as office_config
    from shogun.services import file_formats

    pdf_path = tmp_path / "Input" / "scheduled.pdf"
    pdf_path.parent.mkdir(parents=True)
    pdf_path.write_bytes(b"%PDF-1.4 test fixture")
    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    monkeypatch.setattr(office_config, "load_office_config", lambda: SimpleNamespace(enabled=False))

    class FakeFileFormatService:
        def __init__(self, session=None, allowed_roots=None):
            assert session is None
            assert allowed_roots == [tmp_path.resolve()]

        async def read(self, *, path, start, end, max_chars):
            assert Path(path) == pdf_path.resolve()
            assert (start, end) == (3, 8)
            assert max_chars == settings.agent_flow_document_max_chars
            return {
                "filename": "scheduled.pdf",
                "content": "scheduled PDF content",
                "truncated": False,
                "metadata": {"start_page": 3, "end_page": 8},
                "warnings": [],
            }

    monkeypatch.setattr(file_formats, "FileFormatService", FakeFileFormatService)

    result = await flow_engine._exec_office(
        {
            "action": "pdf_read",
            "input_path": "Input/scheduled.pdf",
            "start_page": 3,
            "end_page": 8,
        },
        "",
    )

    assert "[PDF: scheduled.pdf; pages 3-8]" in result
    assert "scheduled PDF content" in result


@pytest.mark.asyncio
async def test_excel_create_combines_destination_folder_and_filename(tmp_path, monkeypatch):
    from shogun.office import config as office_config

    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    monkeypatch.setattr(office_config, "load_office_config", lambda: SimpleNamespace(enabled=True))

    result = await flow_engine._exec_office(
        {
            "action": "excel_create",
            "output_path": "Output",
            "sheet_name": "Mapped Data",
        },
        "Column A\tColumn B\nOne\tTwo",
    )

    assert (tmp_path / "Output" / "output.xlsx").is_file()
    assert "Output/output.xlsx" in result


@pytest.mark.asyncio
async def test_excel_create_converts_markdown_table_to_columns(tmp_path, monkeypatch):
    import openpyxl

    from shogun.office import config as office_config

    monkeypatch.setattr(settings, "workspace_path", tmp_path)
    monkeypatch.setattr(office_config, "load_office_config", lambda: SimpleNamespace(enabled=True))
    markdown = """Narrative that should not become a worksheet row.

| Item | Quantity | Date |
| --- | ---: | --- |
| 140000 | 26 | 21.07.2026 |
| Item | Quantity | Date |
| 140006 | 3 | 21.07.2026 |
"""

    await flow_engine._exec_office(
        {"action": "excel_create", "output_path": "Output/result.xlsx", "sheet_name": "Mapped Data"},
        markdown,
    )

    workbook = openpyxl.load_workbook(tmp_path / "Output" / "result.xlsx", read_only=True)
    try:
        rows = list(workbook["Mapped Data"].iter_rows(values_only=True))
    finally:
        workbook.close()
    assert rows == [
        ("Item", "Quantity", "Date"),
        ("140000", "26", "21.07.2026"),
        ("140006", "3", "21.07.2026"),
    ]
