"""Durable operator corrections and researched-solution capture."""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any

from sqlalchemy import select

from shogun.db.models.memory_record import MemoryRecord
from shogun.services.memory_service import MemoryService

CORRECTION_PATTERNS = (
    r"^\s*(?:no[,.:;!]|actually[,.:;!]|correction\s*[:,-]|you(?:'re| are) wrong\b)",
    r"^\s*(?:that(?:'s| is) (?:wrong|incorrect|not correct)\b)",
    r"^\s*(?:i meant\b|the correct (?:answer|value|way|version)\b|for future reference\b)",
)


def is_explicit_operator_correction(text: str) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in CORRECTION_PATTERNS)


def _last_assistant_message(history: list[dict[str, Any]]) -> str:
    return next(
        (str(item.get("content") or "") for item in reversed(history) if item.get("role") == "assistant"),
        "",
    )


async def capture_operator_correction(
    *, agent_id: uuid.UUID, user_message: str, history: list[dict[str, Any]], source_type: str
) -> MemoryRecord | None:
    if not is_explicit_operator_correction(user_message):
        return None
    previous = _last_assistant_message(history)
    content = (
        "[Operator correction]\n"
        f"Correction: {user_message.strip()}\n"
        f"Previous Shogun answer: {previous[:2000] if previous else '(not available)'}\n"
        "Use this correction in future answers unless stronger verified evidence supersedes it."
    )
    digest = hashlib.sha256(" ".join(content.lower().split()).encode("utf-8")).hexdigest()

    from shogun.db.engine import async_session_factory

    async with async_session_factory() as session:
        existing = await session.scalar(
            select(MemoryRecord).where(
                MemoryRecord.agent_id == agent_id,
                MemoryRecord.content_hash == digest,
                MemoryRecord.is_archived.is_(False),
            )
        )
        if existing:
            await MemoryService(session).reinforce(existing.id, "confirmed_by_operator", strength=1.5)
            await session.commit()
            return existing
        record = await MemoryService(session).create_memory(
            agent_id=agent_id,
            memory_type="semantic",
            title=f"Operator correction: {user_message.strip()[:100]}",
            content=content,
            source_type=source_type,
            source_system="operator",
            content_hash=digest,
            relevance_score=0.95,
            importance_score=0.9,
            confidence_score=0.9,
            decay_class="slow",
            tags=["operator-correction", "self-reinforced-learning"],
        )
        await session.commit()
        return record


async def capture_researched_solution(
    *, agent_id: uuid.UUID, question: str, solution: str, tool_messages: list[dict[str, Any]]
) -> MemoryRecord | None:
    if not solution.strip():
        return None
    urls = sorted(
        {
            url.rstrip(".,);]")
            for message in tool_messages
            for url in re.findall(r"https?://[^\s\"'<>]+", str(message.get("content") or ""))
        }
    )
    content = (
        "[Verified online research]\n"
        f"Question: {question.strip()}\n"
        f"Solution: {solution.strip()[:6000]}\n"
        f"Sources: {', '.join(urls[:20]) if urls else 'Mado browser research'}"
    )
    digest = hashlib.sha256(" ".join(content.lower().split()).encode("utf-8")).hexdigest()

    from shogun.db.engine import async_session_factory

    async with async_session_factory() as session:
        existing = await session.scalar(
            select(MemoryRecord).where(MemoryRecord.agent_id == agent_id, MemoryRecord.content_hash == digest)
        )
        if existing:
            return existing
        record = await MemoryService(session).create_memory(
            agent_id=agent_id,
            memory_type="procedural",
            title=f"Researched solution: {question.strip()[:100]}",
            content=content,
            source_type="web_research",
            source_system="mado",
            content_hash=digest,
            relevance_score=0.85,
            importance_score=0.75,
            confidence_score=0.8 if urls else 0.65,
            decay_class="slow",
            tags=["researched-solution", "self-reinforced-learning"],
        )
        await session.commit()
        return record
