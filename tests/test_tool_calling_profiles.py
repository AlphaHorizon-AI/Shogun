from __future__ import annotations

from shogun.services.tool_calling_profiles import (
    infer_tool_calling_profile,
    normalize_native_tool_calls,
    normalize_text_tool_calls,
    profile_catalog_payload,
)


def test_ollama_metadata_selects_native_adapter_when_tools_are_advertised():
    profile = infer_tool_calling_profile(
        "gemma4:12b",
        "ollama",
        metadata={"capabilities": ["completion", "vision", "tools"]},
    )

    assert profile["adapter_id"] == "openai_native_v1"
    assert profile["mode"] == "native"
    assert profile["status"] == "detected"
    assert profile["source"] == "ollama_metadata"


def test_ollama_metadata_selects_shogun_fallback_without_native_tools():
    profile = infer_tool_calling_profile(
        "gemma3:12b-it-qat",
        "ollama",
        metadata={"capabilities": ["completion", "vision"]},
    )

    assert profile["adapter_id"] == "shogun_text_v1"
    assert profile["mode"] == "text"
    assert profile["status"] == "fallback"
    assert profile["fallback_enabled"] is True


def test_model_family_inference_prefers_native_gemma4_and_text_gemma3():
    assert infer_tool_calling_profile("gemma4:e4b", "ollama")["mode"] == "native"
    assert infer_tool_calling_profile("gemma3:12b", "ollama")["mode"] == "text"


def test_openai_tool_call_normalizes_to_canonical_shape():
    calls = normalize_native_tool_calls(
        {
            "choices": [
                {
                    "message": {
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "type": "function",
                                "function": {
                                    "name": "echo_tool",
                                    "arguments": '{"text":"hello"}',
                                },
                            }
                        ]
                    }
                }
            ]
        }
    )

    assert calls == [{"id": "call-1", "tool": "echo_tool", "arguments": {"text": "hello"}}]


def test_anthropic_tool_use_normalizes_to_canonical_shape():
    calls = normalize_native_tool_calls(
        {
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu-1",
                    "name": "echo_tool",
                    "input": {"text": "hello"},
                }
            ]
        }
    )

    assert calls == [{"id": "toolu-1", "tool": "echo_tool", "arguments": {"text": "hello"}}]


def test_text_fallback_parses_xml_function_and_canonical_json():
    xml_calls = normalize_text_tool_calls(
        '<tool_call>echo_tool({"text":"hello"})</tool_call>',
        {"echo_tool"},
    )
    json_calls = normalize_text_tool_calls(
        '{"tool":"echo_tool","arguments":{"text":"world"}}',
        {"echo_tool"},
    )

    assert xml_calls[0]["tool"] == "echo_tool"
    assert xml_calls[0]["arguments"] == {"text": "hello"}
    assert json_calls[0]["arguments"] == {"text": "world"}


def test_text_fallback_rejects_unavailable_tool_names():
    assert normalize_text_tool_calls(
        '{"tool":"delete_everything","arguments":{}}',
        {"echo_tool"},
    ) == []


def test_profile_catalog_exposes_versioned_canonical_schema():
    catalog = profile_catalog_payload()

    assert catalog["canonical_schema_id"] == "shogun.tool_call.v1"
    assert catalog["canonical_schema"]["required"] == ["tool", "arguments"]
    assert "openai_native_v1" in catalog["adapters"]
    assert "shogun_text_v1" in catalog["adapters"]
