"""Security and normalization tests for the Katana Teams adapter."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.db.base import Base
from shogun.db.models.operator import Operator
from shogun.db.models.teams import TeamsConfig, TeamsUserMap
from shogun.schemas.teams import ChannelUser, CommandEnvelope
from shogun.services.command_channel import SlidingWindowRateLimiter, authorize, parse_command, strip_teams_mention
from shogun.services.harakiri_control import parse_harakiri_control
from shogun.services.teams_service import DEFAULT_COMMANDS, TeamsService


def test_teams_mention_stripping():
    assert strip_teams_mention("<at>Shogun</at> status") == "status"
    assert strip_teams_mention("@Shogun: show active agents") == "show active agents"


@pytest.mark.parametrize(
    ("text", "name", "risk"),
    [
        ("status", "status", "L0"),
        ("ask samurai-02 summarize today", "ask", "L1"),
        ("run workflow weekly-report with period=this_week", "run", "L2"),
        ("pause agent samurai-02", "pause", "L4"),
        ("harakiri fleet", "harakiri", "L4"),
        ("++hArAkIrI", "harakiri_control", "L4"),
        ("--HARAKIRI", "harakiri_control", "L4"),
        ("approve REQ-12345", "approve", "L3"),
    ],
)
def test_command_parsing_and_risk(text: str, name: str, risk: str):
    parsed = parse_command(text)
    assert parsed.name == name
    assert parsed.risk_level == risk


def test_role_authorization_and_harakiri_gate():
    assert authorize("status", "viewer") == (True, "allowed")
    assert authorize("pause", "viewer")[0] is False
    assert authorize("harakiri", "admin", destructive_commands_enabled=False) == (
        False,
        "destructive_commands_disabled",
    )
    assert authorize("harakiri", "admin", destructive_commands_enabled=True) == (True, "allowed")
    assert authorize("harakiri_control", "viewer")[0] is False
    assert authorize("harakiri_control", "admin", destructive_commands_enabled=False) == (True, "allowed")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("++Harakiri", "activate"),
        (" ++HARAKIRI ", "activate"),
        ("++harakiri", "activate"),
        ("--Harakiri", "reset"),
        (" --hArAkIrI ", "reset"),
        ("please run ++Harakiri", None),
        ("++Harakiri now", None),
        ("Harakiri", None),
    ],
)
def test_exact_harakiri_control_is_case_insensitive(text: str, expected: str | None):
    assert parse_harakiri_control(text) == expected


def test_rate_limit_is_enforced():
    limiter = SlidingWindowRateLimiter()
    assert limiter.allow("user:1", 2)
    assert limiter.allow("user:1", 2)
    assert not limiter.allow("user:1", 2)


def envelope(tenant_id: str, text: str, user_id: str = "teams-user-1") -> CommandEnvelope:
    return CommandEnvelope(
        source="microsoft_teams",
        tenant_id=tenant_id,
        conversation_type="personal",
        message_id=str(uuid4()),
        chat_id="chat-1",
        conversation_reference_id="chat-1",
        user=ChannelUser(teams_user_id=user_id, aad_object_id="aad-1", display_name="Test Admin"),
        raw_text=text,
    )


@pytest.mark.asyncio
async def test_unknown_tenant_rejected_and_audited():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        db.add(TeamsConfig(enabled=True, allowed_tenant_ids=["allowed"], allowed_commands=DEFAULT_COMMANDS))
        await db.flush()
        response = await TeamsService(db).dispatch(envelope("unknown", "status"))
        assert response.response_type == "error"
        assert "not authorized" in response.text
    await engine.dispose()


@pytest.mark.asyncio
async def test_harakiri_approval_is_single_use():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        db.add(
            TeamsConfig(
                enabled=True,
                allowed_tenant_ids=["tenant-1"],
                allowed_commands=DEFAULT_COMMANDS,
                destructive_commands_enabled=True,
                dual_approval_fleet=False,
            )
        )
        db.add(
            TeamsUserMap(
                tenant_id="tenant-1",
                teams_user_id="teams-user-1",
                display_name="Test Admin",
                shogun_role="admin",
            )
        )
        await db.flush()
        service = TeamsService(db)
        proposal = await service.dispatch(envelope("tenant-1", "harakiri fleet"))
        request_id = proposal.card_payload["actions"][0]["data"]["request_id"]
        approved = await service.dispatch(envelope("tenant-1", f"approve {request_id}"))
        reused = await service.dispatch(envelope("tenant-1", f"approve {request_id}"))
        assert approved.severity == "success"
        assert reused.response_type == "error"
        assert "already been used" in reused.text
    await engine.dispose()


@pytest.mark.asyncio
async def test_exact_harakiri_control_executes_immediately_for_admin(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    async def fake_execute(action: str, *, source: str, actor: str) -> dict:
        calls.append((action, source, actor))
        return {"kill_switch_active": action == "activate"}

    monkeypatch.setattr(
        "shogun.services.harakiri_control.execute_harakiri_control",
        fake_execute,
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        db.add(
            TeamsConfig(
                enabled=True,
                allowed_tenant_ids=["tenant-1"],
                allowed_commands=DEFAULT_COMMANDS,
                destructive_commands_enabled=False,
            )
        )
        db.add(
            TeamsUserMap(
                tenant_id="tenant-1",
                teams_user_id="teams-user-1",
                display_name="Test Admin",
                shogun_role="admin",
            )
        )
        await db.flush()

        activated = await TeamsService(db).dispatch(envelope("tenant-1", " ++hArAkIrI "))
        reset = await TeamsService(db).dispatch(envelope("tenant-1", "--HARAKIRI"))

        assert activated.severity == "critical"
        assert reset.severity == "success"
        assert calls == [
            ("activate", "microsoft_teams", "aad-1"),
            ("reset", "microsoft_teams", "aad-1"),
        ]
    await engine.dispose()


@pytest.mark.asyncio
async def test_registered_team_member_can_ask_via_safe_governed_chat(monkeypatch):
    captured: dict = {}

    async def fake_governed_chat(*, user_msg, history, svc, classification):
        captured.update(user_msg=user_msg, history=history, classification=classification)

        async def stream():
            yield 'data: {"type":"token","content":"Hello Alice"}\n\n'
            yield "data: [DONE]\n\n"

        return stream()

    monkeypatch.setattr("shogun.api.governed_chat._shogun_governed_chat", fake_governed_chat)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        db.add(
            TeamsConfig(
                enabled=True,
                allowed_tenant_ids=["tenant-1"],
                allowed_commands=DEFAULT_COMMANDS,
            )
        )
        db.add(
            Operator(
                username="team-2-alice",
                display_name="Alice",
                role="member",
                preferences={
                    "active": True,
                    "teams_user_principal_name": "alice@example.com",
                },
            )
        )
        await db.flush()
        request = envelope("tenant-1", "ask shogun hello", user_id="teams-alice")
        request.user.user_principal_name = "alice@example.com"

        response = await TeamsService(db).dispatch(request)

        user_map = await db.scalar(select(TeamsUserMap))
        assert response.text == "Hello Alice"
        assert user_map.display_name == "Alice"
        assert user_map.shogun_role == "viewer"
        assert user_map.shogun_user_id is not None
        assert captured["classification"]["_speaker_role"] == "Team Member"
        assert "Verified speaker identity" in captured["user_msg"]
    await engine.dispose()
