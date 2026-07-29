import importlib
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shogun.db.base import Base
from shogun.db.models.bushido import ReminderRun, ReminderTask
from shogun.services import reminder_service
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
