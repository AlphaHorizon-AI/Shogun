from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.api import setup as setup_api
from shogun.api.setup import SetupCompletePayload, TeamMemberSetup
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.operator import Operator
from shogun.services import model_router, telegram_poller
from shogun.services.team_identity import member_context_text, resolve_channel_member
from shogun.services.telegram_poller import _effective_telegram_config


def team_payload() -> SetupCompletePayload:
    return SetupCompletePayload(
        security_incident_acknowledged=True,
        operator_name="Michael",
        installation_mode="team",
        team_members=[
            TeamMemberSetup(display_name="Michael", is_primary=True, channel="web"),
            TeamMemberSetup(
                display_name="Alice",
                channel="telegram",
                telegram_user_id="1001",
            ),
            TeamMemberSetup(
                display_name="Bob",
                channel="microsoft_teams",
                teams_user_principal_name="bob@example.com",
            ),
        ],
    )


def test_team_mode_requires_one_admin_and_channel_identity():
    with pytest.raises(ValidationError, match="at least one Team Member"):
        SetupCompletePayload(
            security_incident_acknowledged=True,
            installation_mode="team",
            team_members=[TeamMemberSetup(display_name="Admin", is_primary=True, channel="web")],
        )

    with pytest.raises(ValidationError, match="Telegram user ID"):
        SetupCompletePayload(
            security_incident_acknowledged=True,
            installation_mode="team",
            team_members=[
                TeamMemberSetup(display_name="Admin", is_primary=True, channel="web"),
                TeamMemberSetup(display_name="Alice", channel="telegram"),
            ],
        )


@pytest.mark.asyncio
async def test_team_setup_persists_members_and_pinned_memories(tmp_path, monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    saved_setup: dict = {}
    monkeypatch.setattr(setup_api, "async_session_factory", factory)
    monkeypatch.setattr(setup_api, "_write_setup", lambda data: saved_setup.update(data))
    monkeypatch.setattr(model_router, "_setup_path", lambda: tmp_path / "setup.json")

    await setup_api.complete_setup(team_payload())

    async with factory() as session:
        operators = list((await session.scalars(select(Operator).order_by(Operator.username))).all())
        shogun = await session.scalar(select(Agent).where(Agent.is_primary.is_(True)))
        memories = list(
            (
                await session.scalars(
                    select(MemoryRecord).where(MemoryRecord.source_system == "shogun-setup")
                )
            ).all()
        )

        assert len(operators) == 3
        assert next(item for item in operators if item.username == "admin").role == "owner"
        assert {item.display_name for item in operators if item.role == "member"} == {"Alice", "Bob"}
        assert shogun.bushido_settings["installation_mode"] == "team"
        assert len(shogun.bushido_settings["team_members"]) == 3
        assert len(memories) == 3
        assert all(memory.is_pinned and memory.memory_type == "persona" for memory in memories)
        assert saved_setup["installation_mode"] == "team"
        acknowledgement = saved_setup["security_incident_acknowledgement"]
        assert acknowledgement["record_version"] == 1
        assert acknowledgement["acknowledged_by_role"] == "primary_admin"
        assert acknowledgement["installed_version"]
        assert acknowledgement["installed_build"] is not None
        assert acknowledgement["installed_release_identifier"]
        assert "security and incident reporting information" in acknowledgement["statement"]
        assert datetime.fromisoformat(acknowledgement["acknowledged_at"]).tzinfo is not None

        alice = await resolve_channel_member(session, channel="telegram", external_user_id="1001")
        bob = await resolve_channel_member(
            session,
            channel="microsoft_teams",
            user_principal_name="BOB@example.com",
        )
        assert alice and alice.display_name == "Alice"
        assert bob and bob.display_name == "Bob"
        assert "Team Member" in member_context_text("Hello", alice, channel="Telegram")

    await engine.dispose()


def test_team_telegram_ids_extend_existing_allowlist():
    cfg = _effective_telegram_config(
        {
            "telegram_config": {"allowed_chat_ids": ["admin-chat"]},
            "team_members": [
                {"telegram_user_id": "1001"},
                {"telegram_user_id": "1002"},
                {"teams_user_principal_name": "bob@example.com"},
            ],
        }
    )

    assert cfg["allowed_chat_ids"] == ["admin-chat", "1001", "1002"]


@pytest.mark.asyncio
async def test_team_member_cannot_trigger_telegram_harakiri(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            Operator(
                username="team-2-alice",
                display_name="Alice",
                role="member",
                preferences={"telegram_user_id": "1001", "active": True},
            )
        )
        await session.commit()

    sent: list[str] = []

    async def no_typing(*_args, **_kwargs):
        return None

    async def send(_token, _chat_id, text, **_kwargs):
        sent.append(text)
        return 1

    async def must_not_execute(*_args, **_kwargs):
        raise AssertionError("A Team Member must not execute HARAKIRI")

    monkeypatch.setattr(telegram_poller, "async_session_factory", factory)
    monkeypatch.setattr(telegram_poller, "send_chat_action", no_typing)
    monkeypatch.setattr(telegram_poller, "send_telegram_message", send)
    monkeypatch.setattr("shogun.services.harakiri_control.execute_harakiri_control", must_not_execute)

    await telegram_poller._process_telegram_message(
        "token",
        "chat-1",
        "++harakiri",
        telegram_context={"sender_id": "1001"},
    )

    assert sent == ["⚠️ HARAKIRI is restricted to the Primary Admin."]
    await engine.dispose()
