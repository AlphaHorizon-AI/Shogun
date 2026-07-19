"""Model-grounded OpenClaw College examination runner."""

from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.nexus.protocols.internal_shogun_adapter import InternalShogunAdapter


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise ValueError("The configured model did not return a JSON answer object")
        data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("The configured model returned an invalid exam answer format")
    return data


async def answer_exam_questions(
    db: AsyncSession,
    agent: Any,
    *,
    skill_name: str,
    skill_content: str,
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Have the agent's configured model answer without exposing answer keys."""
    adapter = InternalShogunAdapter(db)
    provider = await adapter._resolve_provider(agent)
    if not provider:
        raise RuntimeError("No connected model provider is available to take the exam")

    candidate_questions = [
        {
            "id": question.get("id"),
            "text": question.get("text", ""),
            "options": question.get("options", []),
        }
        for question in questions
    ]
    system_prompt = """You are taking a closed-book professional certification exam.
Answer from the supplied skill guidance and your domain reasoning. The answer key is not available.
Return JSON only in this shape:
{"answers":{"q-1":"exact option text"},"review":{"rating":4,"strengths":"specific substantive feedback","improvements":"specific substantive feedback","comment":"overall assessment","tags":["clear","challenging"]}}.
Choose exactly one provided option for every question. The review must be genuine, specific to the supplied guidance and exam, and include at least 20 characters in both strengths and improvements. Do not add markdown."""
    user_message = json.dumps(
        {
            "skill": skill_name,
            "skill_guidance": (skill_content or "")[:24000],
            "questions": candidate_questions,
        },
        ensure_ascii=False,
    )
    raw = await adapter._call_llm(provider, system_prompt, user_message)
    payload = _extract_json(raw)
    submitted = payload.get("answers")
    if not isinstance(submitted, dict):
        raise ValueError("The configured model did not return an answers mapping")
    review = payload.get("review")
    if not isinstance(review, dict):
        raise ValueError("The configured model did not return its required post-exam review")
    rating = review.get("rating")
    strengths = str(review.get("strengths") or "").strip()
    improvements = str(review.get("improvements") or "").strip()
    comment = str(review.get("comment") or "").strip()
    if not isinstance(rating, int) or not 1 <= rating <= 5:
        raise ValueError("The configured model returned an invalid review rating")
    if len(strengths) < 20 or len(improvements) < 20:
        raise ValueError("The configured model returned an insufficiently substantive exam review")
    tags = review.get("tags") if isinstance(review.get("tags"), list) else []

    correct = 0
    review: list[dict[str, Any]] = []
    answer_log: list[dict[str, Any]] = []
    for question in questions:
        question_id = str(question.get("id", ""))
        options = [str(item) for item in question.get("options", [])]
        selected = str(submitted.get(question_id, ""))
        if selected not in options:
            selected = ""
        expected = str(question.get("correctAnswer", ""))
        is_correct = bool(selected and expected and selected == expected)
        correct += int(is_correct)
        answer_log.append({"questionId": question_id, "selected": selected, "correct": is_correct})
        review.append(
            {
                "id": question_id,
                "text": question.get("text", ""),
                "options": options,
                "agentAnswer": selected,
                "isCorrect": is_correct,
            }
        )

    total = len(questions)
    return {
        "answers_log": answer_log,
        "questions_review": review,
        "correct": correct,
        "total": total,
        "score": int((correct / total) * 100) if total else 0,
        "provider_id": str(provider.id),
        "provider_name": provider.name,
        "exam_review": {
            "rating": rating,
            "strengths": strengths[:1000],
            "improvements": improvements[:1000],
            "comment": comment[:1000],
            "tags": [str(tag).strip() for tag in tags if str(tag).strip()][:8],
        },
    }
