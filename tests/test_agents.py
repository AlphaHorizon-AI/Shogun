"""Test auto-mode classifier and local-model tool routing."""
from types import SimpleNamespace

from shogun.api.agents import (
    _classify_chat_mode,
    _filter_tools_by_intent,
    _is_small_local_model,
)


def test_nfl_dot_com_routes_to_mission():
    """Domain names like NFL.com must trigger Mission Mode."""
    res = _classify_chat_mode(
        "Could you check the NFL.com for when the frist pre-season match is up and where it is played", []
    )
    assert res["mode"] == "mission", f"Expected mission, got {res}"


def test_plain_greeting_routes_to_fast():
    """Simple greetings must stay in Fast Mode."""
    res = _classify_chat_mode("Hello! How are you today?", [])
    assert res["mode"] == "fast", f"Expected fast, got {res}"


def test_memory_trigger_routes_to_governed():
    """Memory references must route to Governed."""
    res = _classify_chat_mode("Do you remember what I told you last time?", [])
    assert res["mode"] == "governed", f"Expected governed, got {res}"


def test_weather_routes_to_mission():
    """Live-data queries must trigger Mission Mode."""
    res = _classify_chat_mode("What is the weather in Copenhagen?", [])
    assert res["mode"] == "mission", f"Expected mission, got {res}"


def test_https_url_routes_to_mission():
    """Full URLs must trigger Mission Mode."""
    res = _classify_chat_mode("Can you open https://example.org/page for me?", [])
    assert res["mode"] == "mission", f"Expected mission, got {res}"


def test_reminder_language_routes_to_tool_enabled_mission():
    res = _classify_chat_mode("Remind me to review this tomorrow", [])
    assert res["mode"] == "mission"
    assert "remind" in res["matched"]


def test_gemma_12b_is_treated_as_prompt_constrained():
    provider = SimpleNamespace(provider_type="ollama")

    assert _is_small_local_model(provider, "gemma3:12b-it-qat")


def test_word_intent_does_not_expose_other_office_apps():
    tools = [
        {"category": "office", "function": {"name": "office_word_read_page"}},
        {"category": "office", "function": {"name": "office_word_read_pages"}},
        {"category": "office", "function": {"name": "office_word_create"}},
        {"category": "office", "function": {"name": "office_word_create_from_text"}},
        {"category": "office", "function": {"name": "office_excel_open"}},
        {"category": "office", "function": {"name": "office_pptx_open"}},
        {"category": "workspace", "function": {"name": "workspace_list"}},
        {"category": "memory", "function": {"name": "store_memory"}},
    ]

    filtered = _filter_tools_by_intent(
        tools,
        ["document", "translate", "folder"],
        True,
    )
    names = {tool["function"]["name"] for tool in filtered}

    assert "office_word_read_page" in names
    assert "office_word_create_from_text" in names
    assert "workspace_list" not in names
    assert "office_word_read_pages" not in names
    assert "office_word_create" not in names
    assert "office_excel_open" not in names
    assert "office_pptx_open" not in names


def test_document_request_exposes_word_intent_keywords():
    result = _classify_chat_mode(
        "Translate this Word document from the Input folder and save it.",
        [],
    )

    assert result["mode"] == "mission"
    assert "document" in result["matched"]
    assert "word" in result["matched"]
    assert "translate" in result["matched"]
