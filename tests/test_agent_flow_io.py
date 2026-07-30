import uuid
from types import SimpleNamespace

import pytest

from shogun.config import settings
from shogun.engine import flow_engine


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
            assert max_chars == 100000
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


def test_legacy_failure_sentinels_are_real_failures():
    with pytest.raises(RuntimeError, match="Office App Mode is disabled"):
        flow_engine._validated_node_result("[BLOCKED] Office App Mode is disabled")
    with pytest.raises(RuntimeError, match="Permission denied"):
        flow_engine._validated_node_result("[ERROR] Permission denied")


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
