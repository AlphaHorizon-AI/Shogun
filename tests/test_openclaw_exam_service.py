from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from shogun.nexus.protocols.internal_shogun_adapter import InternalShogunAdapter
from shogun.services.openclaw_exam_service import _extract_json, answer_exam_questions


def test_extract_json_accepts_fenced_model_output():
    assert _extract_json('```json\n{"answers": {"q-1": "B"}}\n```') == {"answers": {"q-1": "B"}}


@pytest.mark.asyncio
async def test_exam_model_never_receives_answer_keys(monkeypatch):
    captured: dict[str, str] = {}

    async def fake_call(_self, _provider, _system_prompt, user_message):
        captured["user_message"] = user_message
        return '{"answers":{"q-1":"Use a staged rollout","q-2":"Not an option"}}'

    monkeypatch.setattr(
        InternalShogunAdapter,
        "_resolve_provider",
        AsyncMock(return_value=SimpleNamespace(id="provider-1", name="Test Provider")),
    )
    monkeypatch.setattr(InternalShogunAdapter, "_call_llm", fake_call)

    result = await answer_exam_questions(
        None,
        SimpleNamespace(id="agent-1"),
        skill_name="Safe Deployment",
        skill_content="Validate, stage, observe, and keep rollback evidence.",
        questions=[
            {
                "id": "q-1",
                "text": "How should a risky release begin?",
                "options": ["Deploy globally", "Use a staged rollout"],
                "correctAnswer": "Use a staged rollout",
            },
            {
                "id": "q-2",
                "text": "What evidence is sufficient?",
                "options": ["A passing check", "An assumption"],
                "correctAnswer": "A passing check",
            },
        ],
    )

    assert '"correctAnswer"' not in captured["user_message"]
    assert result["correct"] == 1
    assert result["total"] == 2
    assert result["score"] == 50
    assert result["questions_review"][1]["agentAnswer"] == ""
