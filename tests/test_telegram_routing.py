from shogun.services.telegram_poller import _select_telegram_chat_mode


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
