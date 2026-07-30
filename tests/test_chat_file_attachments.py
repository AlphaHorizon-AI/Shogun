from shogun.api.agents import _chat_attachment_content, _filter_tools_by_intent


def test_file_attachment_manifest_uses_opaque_id_without_server_path():
    content = _chat_attachment_content(
        "Summarize this",
        [{
            "type": "file",
            "file_id": "11111111-1111-1111-1111-111111111111",
            "original_filename": "brief.pdf",
            "format_id": "pdf",
            "size_bytes": 42,
            "path": "C:/private/uploads/internal-name.pdf",
        }],
    )

    assert isinstance(content, str)
    assert "brief.pdf" in content
    assert "11111111-1111-1111-1111-111111111111" in content
    assert "C:/private" not in content


def test_attachment_intent_keeps_file_tools_for_small_models():
    tools = [
        {"category": "files", "function": {"name": "file_read"}},
        {"category": "browser", "function": {"name": "browser_open"}},
        {"category": "memory", "function": {"name": "store_memory"}},
    ]

    filtered = _filter_tools_by_intent(tools, ["attachment"], True)

    assert {tool["function"]["name"] for tool in filtered} == {"file_read", "store_memory"}


def test_attached_document_narrowing_still_keeps_file_reader():
    tools = [
        {"category": "files", "function": {"name": "file_read"}},
        {"category": "office", "function": {"name": "office_word_read_page"}},
        {"category": "browser", "function": {"name": "browser_open"}},
    ]

    filtered = _filter_tools_by_intent(tools, ["attachment", "document"], True)

    assert {tool["function"]["name"] for tool in filtered} == {"file_read", "office_word_read_page"}
