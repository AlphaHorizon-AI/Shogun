"""Persistence helpers for the conversation shared by Comms and Telegram."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.chat_message import ChatMessage


def serialize_chat_message(message: ChatMessage) -> dict:
    return {
        "id": str(message.id),
        "channel": message.channel,
        "role": message.role,
        "content": message.content,
        "external_chat_id": message.external_chat_id,
        "message_data": message.message_data or {},
        "created_at": message.created_at.isoformat(),
    }


async def append_chat_message(
    session: AsyncSession,
    *,
    channel: str,
    role: str,
    content: str,
    external_chat_id: str | None = None,
    client_message_id: str | None = None,
    message_data: dict | None = None,
) -> ChatMessage:
    if client_message_id:
        existing = await session.scalar(
            select(ChatMessage).where(ChatMessage.client_message_id == client_message_id)
        )
        if existing:
            return existing

    message = ChatMessage(
        channel=channel,
        role=role,
        content=content,
        external_chat_id=external_chat_id,
        client_message_id=client_message_id,
        message_data=message_data or {},
    )
    session.add(message)
    await session.flush()
    return message


async def list_chat_messages(session: AsyncSession, *, limit: int = 200) -> list[ChatMessage]:
    result = await session.execute(
        select(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(limit)
    )
    return list(reversed(result.scalars().all()))


def _matches_conversation(message: ChatMessage, context: dict[str, Any]) -> bool:
    """Return whether a Telegram record belongs to the exact active boundary."""
    stored = (message.message_data or {}).get("telegram_context") or {}
    expected_thread = context.get("message_thread_id")
    stored_thread = stored.get("message_thread_id")
    if (str(stored_thread) if stored_thread is not None else None) != (
        str(expected_thread) if expected_thread is not None else None
    ):
        return False
    if str(context.get("chat_type") or "").casefold() == "private":
        expected_sender = str(context.get("sender_id") or "").strip()
        stored_sender = str(stored.get("sender_id") or "").strip()
        return bool(expected_sender) and stored_sender == expected_sender
    return True


async def get_chat_context(
    session: AsyncSession,
    *,
    limit: int = 20,
    channel: str | None = None,
    external_chat_id: str | None = None,
    conversation_context: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    if conversation_context is not None and (not channel or not external_chat_id):
        raise ValueError("Scoped chat context requires channel and external_chat_id")

    if channel or external_chat_id:
        if not channel or not external_chat_id:
            raise ValueError("channel and external_chat_id must be supplied together")
        # The bounded scan may omit old context in very busy conversations, but
        # it can never admit a different conversation or topic.
        result = await session.execute(
            select(ChatMessage)
            .where(
                ChatMessage.channel == channel,
                ChatMessage.external_chat_id == str(external_chat_id),
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(max(limit * 20, 200))
        )
        candidates = list(result.scalars().all())
        if conversation_context is not None:
            candidates = [
                message
                for message in candidates
                if _matches_conversation(message, conversation_context)
            ]
        messages = list(reversed(candidates[:limit]))
    else:
        messages = await list_chat_messages(session, limit=limit)
    return [
        {
            "role": "assistant" if message.role in {"assistant", "shogun"} else "user",
            "content": message.content,
        }
        for message in messages
        if message.role in {"user", "assistant", "shogun"} and message.content.strip()
    ]
