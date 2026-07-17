import uuid
from types import SimpleNamespace

import pytest

from shogun.api.agents import _chat_attachment_content, _resolve_provider_model_id
from shogun.services import telegram_poller
from shogun.services.telegram_poller import (
    _attachment_context_text,
    _prepare_telegram_visual_context,
    _select_telegram_chat_mode,
    _telegram_context_from_message,
    _telegram_context_text,
    _update_topic_registry_from_message,
    list_telegram_topic_mappings,
    set_telegram_topic_mapping,
)


@pytest.mark.asyncio
async def test_telegram_image_is_analyzed_then_removed_from_text_model_payload(monkeypatch):
    artifact_id = uuid.uuid4()

    async def fake_get(self, requested_id):
        assert requested_id == artifact_id
        return SimpleNamespace(id=artifact_id)

    async def fake_analyze(self, artifact, prompt, analysis_type, allow_cloud):
        assert "What is in this image?" in prompt
        assert analysis_type == "telegram_vision"
        assert allow_cloud is True
        return SimpleNamespace(result_text="A person is visible in a portrait photograph.")

    monkeypatch.setattr("shogun.services.visual_intake.VisualIntakeService.get", fake_get)
    monkeypatch.setattr("shogun.services.visual_intake.VisualIntakeService.analyze", fake_analyze)

    prompt, safe_attachments = await _prepare_telegram_visual_context(
        object(),
        "What is in this image?",
        [
            {
                "artifact_id": str(artifact_id),
                "filename": "portrait.jpg",
                "mime_type": "image/jpeg",
                "is_image": True,
            },
            {"filename": "notes.txt", "mime_type": "text/plain"},
        ],
    )

    assert "Governed visual analysis for portrait.jpg" in prompt
    assert "A person is visible" in prompt
    assert safe_attachments == [{"filename": "notes.txt", "mime_type": "text/plain"}]


def test_telegram_defaults_to_tool_capable_mission_mode():
    message, mode, classification = _select_telegram_chat_mode(
        "Please remember my children's birthdays and schedule reminders.",
        [],
    )

    assert message.startswith("Please remember")
    assert mode == "mission"
    assert classification["reason"] == "telegram_mission_default"


def test_telegram_fast_mode_requires_explicit_override():
    message, mode, classification = _select_telegram_chat_mode("/fast Hello there", [])

    assert message == "Hello there"
    assert mode == "fast"
    assert classification["reason"] == "telegram_fast_override"


def test_telegram_auto_override_uses_classifier():
    message, mode, classification = _select_telegram_chat_mode(
        "/auto What is the weather in Copenhagen?",
        [],
    )

    assert message == "What is the weather in Copenhagen?"
    assert mode == "mission"
    assert classification["reason"] == "telegram_auto_override"


def test_telegram_attachment_context_mentions_workspace_path():
    message = _attachment_context_text(
        "What is in this?",
        [
            {
                "filename": "photo.jpg",
                "mime_type": "image/jpeg",
                "size": 123,
                "workspace_path": "Telegram/2026-07-07/123/photo.jpg",
            }
        ],
    )

    assert "What is in this?" in message
    assert "photo.jpg (image/jpeg, 123 bytes)" in message
    assert "Telegram/2026-07-07/123/photo.jpg" in message


def test_chat_attachment_content_includes_image_bytes(tmp_path):
    image_path = tmp_path / "tiny.png"
    image_path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
        b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDAT"
        b"\x08\xd7c\xf8\xff\xff?\x00\x05\xfe\x02\xfeA"
        b"\x89\x8d\xb1\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    content = _chat_attachment_content(
        "Describe this image",
        [{"mime_type": "image/png", "path": str(image_path)}],
    )

    assert isinstance(content, list)
    assert content[0] == {"type": "text", "text": "Describe this image"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/png;base64,")


def test_stale_primary_model_cannot_leak_into_a_different_provider():
    provider = SimpleNamespace(
        id=uuid.uuid4(),
        provider_type="openrouter",
        name="OpenRouter",
        config={"models": ["google/gemini-3.5-flash"]},
    )

    model_id = _resolve_provider_model_id(
        provider,
        saved_model_name="gemma3:12b-it-qat",
        saved_provider_id=str(uuid.uuid4()),
    )

    assert model_id == "google/gemini-3.5-flash"


def test_telegram_topic_registry_remembers_forum_topic(monkeypatch):
    monkeypatch.setattr(telegram_poller, "_topic_registry_cache", {})
    monkeypatch.setattr(telegram_poller, "_save_topic_registry", lambda registry: None)

    _update_topic_registry_from_message(
        {
            "chat": {"id": -100123, "type": "supergroup", "title": "Max Workspace"},
            "message_thread_id": 42,
            "forum_topic_created": {"name": "Operations", "icon_color": 7322096},
        }
    )

    context = _telegram_context_from_message(
        {
            "chat": {"id": -100123, "type": "supergroup", "title": "Max Workspace"},
            "message_thread_id": 42,
            "is_topic_message": True,
            "text": "Can you see this topic?",
        }
    )

    assert context["chat_title"] == "Max Workspace"
    assert context["message_thread_id"] == 42
    assert context["topic_name"] == "Operations"
    assert context["known_topics"] == [
        {
            "message_thread_id": 42,
            "name": "Operations",
            "status": "open",
        }
    ]


def test_telegram_context_text_includes_group_and_topic():
    message = _telegram_context_text(
        "Can you see the group?",
        {
            "chat_title": "Max Workspace",
            "chat_type": "supergroup",
            "message_thread_id": 42,
            "topic_name": "Operations",
            "known_topics": [{"message_thread_id": 42, "name": "Operations", "status": "open"}],
        },
    )

    assert "Can you see the group?" in message
    assert "Chat: Max Workspace (supergroup)" in message
    assert "Topic/thread id: 42" in message
    assert "Known topics in this chat: Operations [42]" in message


def test_ordinary_forum_message_registers_thread_and_tag_name(monkeypatch):
    monkeypatch.setattr(telegram_poller, "_topic_registry_cache", {})
    monkeypatch.setattr(telegram_poller, "_save_topic_registry", lambda registry: None)

    _update_topic_registry_from_message(
        {
            "chat": {"id": -1001, "type": "supergroup", "title": "Alpha Horizon"},
            "message_thread_id": 73,
            "is_topic_message": True,
            "text": "*strategy Review the quarterly plan",
        }
    )

    context = _telegram_context_from_message(
        {
            "chat": {"id": -1001, "type": "supergroup", "title": "Alpha Horizon"},
            "message_thread_id": 73,
            "is_topic_message": True,
            "text": "What did we decide?",
        }
    )
    assert context["message_thread_id"] == 73
    assert context["topic_name"] == "Alpha Horizon Strategy"
    assert context["topic_name_source"] == "tag:strategy"


def test_manual_topic_mapping_is_durable_in_registry(monkeypatch):
    monkeypatch.setattr(telegram_poller, "_topic_registry_cache", {})
    monkeypatch.setattr(telegram_poller, "_save_topic_registry", lambda registry: None)

    set_telegram_topic_mapping("-1002", 99, "Education and Skills")
    groups = list_telegram_topic_mappings()

    assert groups[0]["chat_id"] == "-1002"
    assert groups[0]["topics"][0]["message_thread_id"] == 99
    assert groups[0]["topics"][0]["name"] == "Education and Skills"
