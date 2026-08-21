from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.db.models.chat_message import ChatMessage
from shogun.services.chat_sync_service import (
    append_chat_message,
    get_chat_context,
    list_chat_messages,
)

ROOT = Path(__file__).resolve().parents[1]


async def _sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: ChatMessage.__table__.create(sync_connection)
        )
    return engine, async_sessionmaker(engine, expire_on_commit=False)


@pytest.mark.asyncio
async def test_comms_and_telegram_share_ordered_context():
    engine, sessions = await _sessions()
    async with sessions() as session:
        await append_chat_message(
            session,
            channel="comms",
            role="user",
            content="Plan the launch",
            client_message_id="web-1",
        )
        await append_chat_message(
            session,
            channel="telegram",
            role="assistant",
            content="I will draft it.",
            external_chat_id="123",
        )
        await session.commit()

        messages = await list_chat_messages(session)
        context = await get_chat_context(session)

    assert [message.channel for message in messages] == ["comms", "telegram"]
    assert context == [
        {"role": "user", "content": "Plan the launch"},
        {"role": "assistant", "content": "I will draft it."},
    ]
    await engine.dispose()


@pytest.mark.asyncio
async def test_client_message_id_makes_web_sync_idempotent():
    engine, sessions = await _sessions()
    async with sessions() as session:
        first = await append_chat_message(
            session,
            channel="comms",
            role="user",
            content="Hello",
            client_message_id="same-id",
        )
        second = await append_chat_message(
            session,
            channel="comms",
            role="user",
            content="Hello",
            client_message_id="same-id",
        )
        assert first.id == second.id
        assert len(await list_chat_messages(session)) == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_telegram_private_chat_context_is_principal_and_chat_scoped():
    engine, sessions = await _sessions()
    async with sessions() as session:
        for chat_id, sender_id, content in (
            ("alice-chat", "alice", "Alice private context"),
            ("bob-chat", "bob", "Bob private context"),
        ):
            context = {
                "chat_id": chat_id,
                "chat_type": "private",
                "sender_id": sender_id,
                "message_thread_id": None,
            }
            await append_chat_message(
                session,
                channel="telegram",
                role="user",
                content=content,
                external_chat_id=chat_id,
                message_data={"telegram_context": context},
            )
        await session.commit()

        bob = await get_chat_context(
            session,
            channel="telegram",
            external_chat_id="bob-chat",
            conversation_context={
                "chat_id": "bob-chat",
                "chat_type": "private",
                "sender_id": "bob",
                "message_thread_id": None,
            },
        )

    assert bob == [{"role": "user", "content": "Bob private context"}]
    await engine.dispose()


@pytest.mark.asyncio
async def test_telegram_group_history_isolated_by_forum_topic():
    engine, sessions = await _sessions()
    async with sessions() as session:
        for thread_id, content in (("10", "Topic ten"), ("20", "Topic twenty")):
            context = {
                "chat_id": "shared-group",
                "chat_type": "supergroup",
                "sender_id": "member",
                "message_thread_id": thread_id,
            }
            await append_chat_message(
                session,
                channel="telegram",
                role="user",
                content=content,
                external_chat_id="shared-group",
                message_data={"telegram_context": context},
            )
        await session.commit()

        topic_twenty = await get_chat_context(
            session,
            channel="telegram",
            external_chat_id="shared-group",
            conversation_context={
                "chat_id": "shared-group",
                "chat_type": "supergroup",
                "sender_id": "other-member",
                "message_thread_id": "20",
            },
        )

    assert topic_twenty == [{"role": "user", "content": "Topic twenty"}]
    await engine.dispose()


def test_telegram_runtime_requests_scoped_history() -> None:
    source = (ROOT / "shogun" / "services" / "telegram_poller.py").read_text(
        encoding="utf-8"
    )
    call = source.split("history = await get_chat_context(", maxsplit=1)[1].split(
        "await append_chat_message", maxsplit=1
    )[0]
    assert 'channel="telegram"' in call
    assert "external_chat_id=chat_id" in call
    assert "conversation_context=telegram_context" in call
