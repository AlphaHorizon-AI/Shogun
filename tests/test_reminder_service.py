import importlib
import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.db.base import Base
from shogun.db.models.agent import Agent
from shogun.db.models.bushido import ReminderRun, ReminderTask
from shogun.services import reminder_service
from shogun.services.native_skills import NATIVE_TOOLS, execute_native_tool
from shogun.services.reminder_service import (
    ReminderService,
    calculate_next_run,
    parse_reminder_text,
    process_due_reminders,
)


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        yield db
    await engine.dispose()


def test_daily_reminder_respects_local_timezone():
    task = ReminderTask(
        title="Daily stand-up",
        schedule_type="daily",
        schedule_time="09:00",
        timezone="Europe/Copenhagen",
    )
    next_run = calculate_next_run(
        task,
        after=datetime(2026, 7, 30, 6, 0, tzinfo=timezone.utc),
        initial=True,
    )
    assert next_run == datetime(2026, 7, 30, 7, 0, tzinfo=timezone.utc)


def test_parser_supports_common_recurring_phrases():
    parsed = parse_reminder_text(
        "Submit timesheet every weekday at 4:30 pm",
        "Europe/Copenhagen",
        now=datetime(2026, 7, 30, 8, 0, tzinfo=timezone.utc),
    )
    assert parsed["schedule_type"] == "weekdays"
    assert parsed["schedule_time"] == "16:30"

    interval = parse_reminder_text("Check the build every 30 minutes", "UTC")
    assert interval["schedule_type"] == "interval"
    assert interval["interval_minutes"] == 30

    relative = parse_reminder_text(
        "Check the upload in 30 minutes",
        "UTC",
        now=datetime(2026, 7, 30, 8, 0, tzinfo=timezone.utc),
    )
    assert relative["run_at"] == "2026-07-30T08:30:00+00:00"


@pytest.mark.asyncio
async def test_reminder_lifecycle_is_durable(session):
    service = ReminderService(session)
    reminder = await service.create(
        title="Check the deployment",
        schedule_type="one_time",
        timezone="UTC",
        run_at=datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc),
    )
    await session.commit()

    assert reminder.next_run_at == datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    await service.transition(reminder.id, "snooze", snooze_minutes=10)
    assert reminder.status == "snoozed"
    assert reminder.next_run_at == reminder.snoozed_until

    await service.transition(reminder.id, "pause")
    assert reminder.status == "paused"
    assert reminder.next_run_at is None

    await service.transition(reminder.id, "resume")
    assert reminder.status == "active"
    assert reminder.next_run_at is not None

    await service.transition(reminder.id, "complete")
    await session.commit()
    assert reminder.status == "completed"
    assert reminder.next_run_at is None


@pytest.mark.asyncio
async def test_due_scanner_claims_and_records_delivery(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reminders.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    db_engine_module = importlib.import_module("shogun.db.engine")
    monkeypatch.setattr(db_engine_module, "async_session_factory", factory)

    async def delivered(_task):
        return {"web": {"id": "notification-1"}}

    monkeypatch.setattr(reminder_service, "_deliver", delivered)
    async with factory() as db:
        db.add(
            ReminderTask(
                title="Due reminder",
                schedule_type="one_time",
                timezone="UTC",
                delivery_channel="web",
                run_at=datetime(2020, 1, 1, 7, 0, tzinfo=timezone.utc),
                next_run_at=datetime(2020, 1, 1, 7, 0, tzinfo=timezone.utc),
            )
        )
        await db.commit()

    assert await process_due_reminders() == 1
    async with factory() as db:
        task = await db.scalar(select(ReminderTask))
        run = await db.scalar(select(ReminderRun))
        assert task.status == "completed"
        assert task.occurrence_count == 1
        assert run.status == "delivered"
        assert run.delivery_result["web"]["id"] == "notification-1"
    await engine.dispose()


@pytest.mark.asyncio
async def test_ai_obligation_is_deduplicated_and_injected_into_prompt(session):
    service = ReminderService(session)
    agent_id = __import__("uuid").uuid4()
    review_at = datetime(2026, 8, 2, 12, 0, tzinfo=timezone.utc)
    first, created = await service.create_ai_obligation(
        title="Review failed college exam", review_at=review_at, agent_id=agent_id,
        item_type="follow_up", reason="The exam attempt remains unresolved",
    )
    duplicate, created_again = await service.create_ai_obligation(
        title="  review FAILED college exam ", review_at=review_at, agent_id=agent_id,
        reason="Duplicate wording",
    )
    context = await service.prompt_context(agent_id=agent_id)
    assert created is True
    assert created_again is False
    assert duplicate.id == first.id
    assert "Review failed college exam" in context
    assert "follow_up" in context
    assert "remains unresolved" in context


@pytest.mark.asyncio
async def test_due_ai_obligation_remains_open(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'ai-obligations.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(importlib.import_module("shogun.db.engine"), "async_session_factory", factory)

    async def delivered(_task):
        return {"web": {"id": "notification-ai"}}

    monkeypatch.setattr(reminder_service, "_deliver", delivered)
    async with factory() as db:
        db.add(ReminderTask(
            title="Review obligation", origin="ai", item_type="obligation",
            schedule_type="one_time", timezone="UTC",
            run_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            next_run_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        ))
        await db.commit()
    assert await process_due_reminders() == 1
    async with factory() as db:
        task = await db.scalar(select(ReminderTask))
        assert task.status == "due"
        assert task.next_run_at is None
    await engine.dispose()


def test_native_tools_expose_operational_reminder_board():
    tools = {tool["function"]["name"]: tool for tool in NATIVE_TOOLS}
    assert tools["reminder_board_add"]["risk"] == "medium"
    assert tools["reminder_board_list"]["risk"] == "low"
    assert tools["reminder_board_update"]["function"]["parameters"]["required"] == ["task_id", "action"]


@pytest.mark.asyncio
async def test_native_ai_tool_creates_owned_obligation(session):
    agent = Agent(
        agent_type="shogun", name="Shogun", slug="primary-shogun",
        status="active", is_primary=True,
    )
    session.add(agent)
    await session.commit()
    result = json.loads(await execute_native_tool(
        "reminder_board_add",
        {
            "title": "Check the pending result",
            "reason": "The result is not available yet",
            "item_type": "check",
            "review_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
        session,
    ))
    task = await session.get(ReminderTask, __import__("uuid").UUID(result["task_id"]))
    assert result["status"] == "success"
    assert task is not None
    assert task.origin == "ai"
    assert task.agent_id == agent.id
    assert task.reason == "The result is not available yet"
