from __future__ import annotations

import pytest

from shogun.services.model_reasoning import (
    apply_chat_reasoning,
    reasoning_capability,
    validate_model_reasoning_config,
)


def test_openai_model_exposes_exact_reasoning_choices() -> None:
    capability = reasoning_capability("openai", "gpt-5.6")

    assert capability is not None
    assert capability["supported_efforts"] == ["none", "low", "medium", "high", "xhigh", "max"]
    assert capability["provider_default"] == "medium"


def test_openrouter_openai_model_uses_openai_reasoning_catalog() -> None:
    capability = reasoning_capability("openrouter", "openai/gpt-5.2")

    assert capability is not None
    assert "xhigh" in capability["supported_efforts"]


def test_reasoning_is_applied_and_incompatible_sampling_is_removed() -> None:
    payload = {"model": "gpt-5.2", "messages": [], "temperature": 0.7, "top_p": 0.9}

    selected = apply_chat_reasoning(
        payload,
        provider_type="openai",
        model_id="gpt-5.2",
        provider_config={"model_reasoning": {"gpt-5.2": "high"}},
    )

    assert selected == "high"
    assert payload["reasoning_effort"] == "high"
    assert "temperature" not in payload
    assert "top_p" not in payload


def test_invalid_reasoning_choice_is_rejected_before_save() -> None:
    with pytest.raises(ValueError, match="does not support reasoning effort"):
        validate_model_reasoning_config(
            "openai",
            {"models": ["gpt-5.6"], "model_reasoning": {"gpt-5.6": "minimal"}},
        )


def test_reasoning_must_reference_a_selected_model() -> None:
    with pytest.raises(ValueError, match="unselected model"):
        validate_model_reasoning_config(
            "openai",
            {"models": ["gpt-5.6"], "model_reasoning": {"gpt-5.2": "high"}},
        )
