from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import shogun.db.models  # noqa: F401
from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.operator import Operator
from shogun.api.deps import get_db
from shogun.app import create_app
from shogun.services.team_identity import (
    add_team_member,
    configured_telegram_member_ids,
    delete_team_member,
    get_team_state,
    resolve_channel_member,
    set_team_mode,
)


@pytest.fixture
async def team_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        agent = Agent(
            agent_type="shogun",
            name="Shogun",
            slug="primary-team-manager",
            status="active",
            is_primary=True,
            bushido_settings={"installation_mode": "single", "team_members": []},
        )
        admin = Operator(
            username="admin",
            display_name="Michael",
            role="owner",
            preferences={
                "setup_managed": True,
                "installation_mode": "single",
                "is_primary": True,
                "active": True,
                "channel": "web",
            },
        )
        session.add_all([agent, admin])
        await session.commit()
        yield session, agent, admin
    await engine.dispose()


@pytest.mark.asyncio
async def test_katana_can_switch_modes_add_and_delete_members(team_session):
    session, agent, admin = team_session

    team_state = await set_team_mode(session, "team")
    assert team_state["mode"] == "team"

    alice = await add_team_member(
        session,
        member={
            "display_name": "Alice",
            "email": "alice@example.com",
            "channel": "telegram",
            "telegram_user_id": "1001",
        },
    )
    assert alice["active"] is True
    assert alice["role"] == "member"
    await session.refresh(agent)
    assert configured_telegram_member_ids(agent.bushido_settings) == ["1001"]
    assert (await resolve_channel_member(session, channel="telegram", external_user_id="1001")) is not None

    single_state = await set_team_mode(session, "single")
    assert single_state["mode"] == "single"
    assert next(item for item in single_state["members"] if item["display_name"] == "Alice")["active"] is False
    await session.refresh(agent)
    assert configured_telegram_member_ids(agent.bushido_settings) == []
    assert await resolve_channel_member(session, channel="telegram", external_user_id="1001") is None

    restored = await set_team_mode(session, "team")
    assert next(item for item in restored["members"] if item["display_name"] == "Alice")["active"] is True
    assert await resolve_channel_member(session, channel="telegram", external_user_id="1001") is not None

    deleted = await delete_team_member(session, uuid.UUID(alice["id"]))
    assert deleted["deleted"] is True
    assert all(item["id"] != alice["id"] for item in (await get_team_state(session))["members"])
    assert await resolve_channel_member(session, channel="telegram", external_user_id="1001") is None
    identity_memory = await session.scalar(
        select(MemoryRecord).where(MemoryRecord.source_external_id == f"team-member:{alice['id']}")
    )
    assert identity_memory is not None
    assert identity_memory.is_archived is True
    assert identity_memory.is_pinned is False

    with pytest.raises(ValueError, match="Primary Admin cannot be deleted"):
        await delete_team_member(session, admin.id)


@pytest.mark.asyncio
async def test_member_identity_must_be_unique_and_team_mode_active(team_session):
    session, _agent, _admin = team_session
    with pytest.raises(ValueError, match="Switch to Team mode"):
        await add_team_member(
            session,
            member={"display_name": "Alice", "channel": "telegram", "telegram_user_id": "1001"},
        )

    await set_team_mode(session, "team")
    await add_team_member(
        session,
        member={"display_name": "Alice", "channel": "telegram", "telegram_user_id": "1001"},
    )
    with pytest.raises(ValueError, match="already belongs"):
        await add_team_member(
            session,
            member={"display_name": "Alice 2", "channel": "telegram", "telegram_user_id": "1001"},
        )


@pytest.mark.asyncio
async def test_katana_team_api_lifecycle(team_session):
    session, _agent, admin = team_session
    app = create_app()

    async def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        initial = await client.get("/api/v1/team")
        assert initial.status_code == 200
        assert initial.json()["data"]["mode"] == "single"

        switched = await client.put("/api/v1/team/mode", json={"mode": "team"})
        assert switched.status_code == 200
        assert switched.json()["data"]["mode"] == "team"

        created = await client.post("/api/v1/team/members", json={
            "display_name": "Beatrice",
            "channel": "microsoft_teams",
            "teams_user_principal_name": "beatrice@example.com",
        })
        assert created.status_code == 201
        member_id = created.json()["data"]["id"]

        protected = await client.delete(f"/api/v1/team/members/{admin.id}")
        assert protected.status_code == 422
        removed = await client.delete(f"/api/v1/team/members/{member_id}")
        assert removed.status_code == 200
        assert removed.json()["data"]["deleted"] is True

    app.dependency_overrides.clear()
