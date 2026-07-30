"""Durable L0 reminder scheduling and delivery for the Bushido Reminder Board."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.bushido import ReminderRun, ReminderTask

log = logging.getLogger(__name__)

ACTIVE_STATUSES = {"active", "snoozed"}
OPEN_STATUSES = {"active", "snoozed", "paused", "due"}
FINAL_STATUSES = {"completed", "cancelled", "expired"}

REMINDER_BOARD_GUIDE = """REMINDER BOARD — operational short-term memory:
- Use reminder_board_add for a concrete unresolved future obligation, follow-up,
  check, or deferred action that Shogun must revisit.
- Do not add ordinary facts, conversation summaries, uncommitted ideas,
  speculation, or completed work. Durable knowledge belongs in Archives.
- Record direct, unambiguous operator requests immediately. If an inferred
  obligation is uncertain, ask before creating it.
- Avoid duplicates. Include a review time and concise reason. Resolve or
  reschedule an item when its outcome is known.
- The board tracks obligations; it does not execute external work. Use the
  appropriate governed tool or AgentFlow for execution."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return _utc(value)


def _calendar_candidate(task: ReminderTask, after: datetime) -> datetime:
    zone = ZoneInfo(task.timezone)
    local_after = _utc(after).astimezone(zone)
    hour, minute = (int(part) for part in (task.schedule_time or "09:00").split(":"))
    allowed = set(task.schedule_days or [])
    if task.schedule_type == "weekdays":
        allowed = {0, 1, 2, 3, 4}
    elif task.schedule_type == "daily":
        allowed = set(range(7))

    for offset in range(0, 8):
        day = local_after.date() + timedelta(days=offset)
        candidate = datetime.combine(day, time(hour, minute), tzinfo=zone)
        if candidate <= local_after or candidate.weekday() not in allowed:
            continue
        return candidate.astimezone(timezone.utc)
    raise ValueError("No next calendar occurrence could be calculated")


def calculate_next_run(task: ReminderTask, *, after: datetime | None = None, initial: bool = False) -> datetime | None:
    """Calculate the next UTC occurrence for a validated reminder."""
    now = _utc(after or datetime.now(timezone.utc))
    if task.schedule_type == "one_time":
        return _as_aware_utc(task.run_at) if initial else None
    if task.schedule_type == "interval":
        if initial and task.run_at and _utc(task.run_at) > now:
            return _utc(task.run_at)
        return now + timedelta(minutes=task.interval_minutes or 1)
    return _calendar_candidate(task, now)


class ReminderService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, **data) -> ReminderTask:
        task = ReminderTask(**data)
        task.next_run_at = calculate_next_run(task, initial=True)
        self.session.add(task)
        await self.session.flush()
        return task

    async def create_ai_obligation(
        self,
        *,
        title: str,
        review_at: datetime,
        agent_id: uuid.UUID | None,
        description: str | None = None,
        item_type: str = "obligation",
        reason: str | None = None,
        confidence: float = 1.0,
        expires_at: datetime | None = None,
        source_message_id: str | None = None,
        priority: int = 50,
    ) -> tuple[ReminderTask, bool]:
        """Create an AI obligation, suppressing duplicate unresolved titles."""
        normalized = " ".join(title.lower().split())
        result = await self.session.execute(
            select(ReminderTask).where(
                ReminderTask.origin == "ai",
                ReminderTask.status.in_(OPEN_STATUSES),
                ReminderTask.agent_id == agent_id,
            )
        )
        for existing in result.scalars():
            if " ".join(existing.title.lower().split()) == normalized:
                return existing, False
        task = await self.create(
            title=title.strip(),
            description=description,
            origin="ai",
            item_type=item_type,
            reason=reason,
            confidence=confidence,
            expires_at=expires_at,
            source_message_id=source_message_id,
            agent_id=agent_id,
            priority=priority,
            schedule_type="one_time",
            timezone="UTC",
            run_at=_utc(review_at),
            delivery_channel="web",
        )
        return task, True

    async def prompt_context(
        self,
        *,
        agent_id: uuid.UUID | None,
        user_id: str = "local_user",
        limit: int = 10,
    ) -> str:
        """Return a compact prompt-safe view of unresolved operational items."""
        now = datetime.now(timezone.utc)
        result = await self.session.execute(
            select(ReminderTask)
            .where(
                ReminderTask.status.in_(OPEN_STATUSES),
                or_(ReminderTask.agent_id == agent_id, ReminderTask.user_id == user_id),
            )
            .order_by(ReminderTask.priority.desc(), ReminderTask.next_run_at.is_(None), ReminderTask.next_run_at)
            .limit(limit)
        )
        items = []
        for task in result.scalars():
            if task.expires_at and _utc(task.expires_at) <= now:
                task.status = "expired"
                task.next_run_at = None
                continue
            review = _as_aware_utc(task.next_run_at or task.run_at)
            when = review.isoformat() if review else task.status
            reason = f"; reason={task.reason[:180]}" if task.reason else ""
            items.append(
                f"- id={task.id}; {task.origin}/{task.item_type}; status={task.status}; "
                f"review={when}; title={task.title[:240]}{reason}"
            )
        await self.session.flush()
        if not items:
            return "REMINDER BOARD — unresolved items: none."
        return "REMINDER BOARD — unresolved items:\n" + "\n".join(items)

    async def get(self, task_id: uuid.UUID) -> ReminderTask | None:
        return await self.session.get(ReminderTask, task_id)

    async def list(
        self,
        *,
        status: str | None = None,
        user_id: str | None = None,
        tenant_id: str | None = None,
        limit: int = 200,
    ) -> list[ReminderTask]:
        query = select(ReminderTask)
        if status:
            query = query.where(ReminderTask.status == status)
        if user_id:
            query = query.where(ReminderTask.user_id == user_id)
        if tenant_id:
            query = query.where(ReminderTask.tenant_id == tenant_id)
        result = await self.session.execute(
            query.order_by(
                ReminderTask.next_run_at.is_(None),
                ReminderTask.next_run_at,
                ReminderTask.created_at.desc(),
            ).limit(limit)
        )
        return list(result.scalars().all())

    async def update(self, task_id: uuid.UUID, **data) -> ReminderTask | None:
        task = await self.get(task_id)
        if not task:
            return None
        for key, value in data.items():
            setattr(task, key, value)
        await self.session.flush()
        return task

    async def transition(
        self,
        task_id: uuid.UUID,
        action: str,
        *,
        snooze_minutes: int | None = None,
    ) -> ReminderTask | None:
        task = await self.get(task_id)
        if not task:
            return None
        now = datetime.now(timezone.utc)
        if action == "pause" and task.status in OPEN_STATUSES:
            task.status = "paused"
            task.next_run_at = None
        elif action == "resume" and task.status == "paused":
            task.snoozed_until = None
            if task.schedule_type == "one_time" and task.occurrence_count > 0 and task.origin in {"ai", "system"}:
                task.status = "due"
                task.next_run_at = None
            else:
                task.status = "active"
                task.next_run_at = calculate_next_run(task, after=now, initial=task.occurrence_count == 0)
        elif action == "snooze" and task.status in OPEN_STATUSES:
            task.status = "snoozed"
            task.snoozed_until = now + timedelta(minutes=snooze_minutes or 10)
            task.next_run_at = task.snoozed_until
        elif action in {"cancel", "complete"} and task.status not in FINAL_STATUSES:
            task.status = "cancelled" if action == "cancel" else "completed"
            task.next_run_at = None
            task.snoozed_until = None
        else:
            raise ValueError(f"Cannot {action} a reminder in status '{task.status}'")
        task.lock_owner = None
        task.lock_until = None
        await self.session.flush()
        return task

    async def runs(self, task_id: uuid.UUID, limit: int = 100) -> list[ReminderRun]:
        result = await self.session.execute(
            select(ReminderRun)
            .where(ReminderRun.task_id == task_id)
            .order_by(ReminderRun.scheduled_for.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def _deliver(task: ReminderTask) -> dict:
    from shogun.services.notification_service import publish_notification, send_channel_message

    message = task.title if not task.description else f"{task.title}\n\n{task.description}"
    result: dict = {}
    if task.delivery_channel in {"web", "both"}:
        result["web"] = publish_notification(
            event_type="reminder.due",
            title="Reminder",
            message=message,
            severity="info",
            detail={"reminder_id": str(task.id), "user_id": task.user_id},
        )
    if task.delivery_channel in {"telegram", "teams", "both"}:
        channel = task.delivery_channel
        telegram_ids = [task.conversation_id] if channel in {"telegram", "both"} and task.conversation_id else None
        teams_ids = [task.conversation_id] if channel in {"teams", "both"} and task.conversation_id else None
        external = await send_channel_message(
            f"REMINDER: {message}",
            channel=channel,
            telegram_chat_ids=telegram_ids,
            telegram_message_thread_id=int(task.topic_id) if task.topic_id and task.topic_id.isdigit() else None,
            teams_conversation_ids=teams_ids,
            event_type="reminder.due",
        )
        result.update(external)
    return result


def _delivery_succeeded(task: ReminderTask, result: dict) -> bool:
    if task.delivery_channel == "web":
        return "web" in result
    expected = {"telegram", "teams"} if task.delivery_channel == "both" else {task.delivery_channel}
    return all(bool(result.get(channel, {}).get("ok")) for channel in expected)


async def process_due_reminders(batch_size: int = 50) -> int:
    """Claim and deliver due reminders. Safe against overlapping scanner instances."""
    from shogun.db.engine import async_session_factory

    now = datetime.now(timezone.utc)
    owner = uuid.uuid4().hex
    async with async_session_factory() as session:
        result = await session.execute(
            select(ReminderTask.id)
            .where(
                ReminderTask.status.in_(ACTIVE_STATUSES),
                ReminderTask.next_run_at.is_not(None),
                ReminderTask.next_run_at <= now,
                or_(ReminderTask.lock_until.is_(None), ReminderTask.lock_until < now),
            )
            .order_by(ReminderTask.next_run_at)
            .limit(batch_size)
        )
        candidate_ids = list(result.scalars().all())

    processed = 0
    for task_id in candidate_ids:
        async with async_session_factory() as session:
            claim = await session.execute(
                update(ReminderTask)
                .where(
                    ReminderTask.id == task_id,
                    ReminderTask.status.in_(ACTIVE_STATUSES),
                    ReminderTask.next_run_at.is_not(None),
                    ReminderTask.next_run_at <= now,
                    or_(ReminderTask.lock_until.is_(None), ReminderTask.lock_until < now),
                )
                .values(lock_owner=owner, lock_until=now + timedelta(minutes=5))
            )
            await session.commit()
            if claim.rowcount != 1:
                continue

        async with async_session_factory() as session:
            task = await session.get(ReminderTask, task_id)
            if not task or task.lock_owner != owner:
                continue
            scheduled_for = _as_aware_utc(task.next_run_at) or now
            run = ReminderRun(
                task_id=task.id,
                scheduled_for=scheduled_for,
                started_at=datetime.now(timezone.utc),
                status="running",
                occurrence_number=task.occurrence_count + 1,
                correlation_id=f"reminder-{uuid.uuid4().hex}",
            )
            session.add(run)
            await session.commit()
            try:
                delivery = await _deliver(task)
                ok = _delivery_succeeded(task, delivery)
                run.delivery_result = delivery
                run.status = "delivered" if ok else "failed"
                if not ok:
                    run.error = "One or more configured delivery channels failed"
            except Exception as exc:
                log.exception("Reminder delivery failed for %s", task.id)
                run.status = "failed"
                run.error = str(exc)[:4000]
            run.completed_at = datetime.now(timezone.utc)
            task.last_run_at = run.completed_at
            task.occurrence_count += 1
            task.snoozed_until = None
            task.lock_owner = None
            task.lock_until = None
            exhausted = bool(task.max_occurrences and task.occurrence_count >= task.max_occurrences)
            ended = bool(task.end_at and _utc(task.end_at) <= run.completed_at)
            if task.schedule_type == "one_time" or exhausted or ended:
                # Agent obligations remain open after notification. Their due
                # time is a review point, not proof that the work is complete.
                task.status = "due" if task.origin in {"ai", "system"} else "completed"
                task.next_run_at = None
            else:
                task.status = "active"
                # Skip stale recurring occurrences after downtime instead of
                # replaying every missed reminder on successive scanner ticks.
                task.next_run_at = calculate_next_run(task, after=run.completed_at)
            await session.commit()
            processed += 1
    return processed


_TIME_RE = re.compile(r"\b(?:at\s+)?(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<ampm>am|pm)?\b", re.I)


def parse_reminder_text(text: str, timezone_name: str, *, now: datetime | None = None) -> dict:
    """Deterministically parse the small, documented MVP reminder grammar."""
    zone = ZoneInfo(timezone_name)
    local_now = _utc(now or datetime.now(timezone.utc)).astimezone(zone)
    lowered = text.strip().lower()
    payload: dict = {"title": text.strip(), "timezone": timezone_name, "delivery_channel": "web"}

    relative = re.search(r"\bin\s+(\d+)\s*(minute|minutes|hour|hours|day|days)\b", lowered)
    if relative:
        amount = int(relative.group(1))
        unit = relative.group(2)
        delta = timedelta(
            days=amount if unit.startswith("day") else 0,
            hours=amount if unit.startswith("hour") else 0,
            minutes=amount if unit.startswith("minute") else 0,
        )
        payload.update(schedule_type="one_time", run_at=(local_now + delta).astimezone(timezone.utc).isoformat())
        return payload

    interval = re.search(r"every\s+(\d+)\s*(minute|minutes|hour|hours)\b", lowered)
    match = None if interval else _TIME_RE.search(lowered)
    hour, minute = 9, 0
    if match:
        hour = int(match.group("hour"))
        minute = int(match.group("minute") or 0)
        ampm = match.group("ampm")
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
        if hour > 23 or minute > 59:
            raise ValueError("The reminder time is invalid")

    schedule_type = "one_time"
    if "every weekday" in lowered or "weekdays" in lowered:
        schedule_type = "weekdays"
    elif "every day" in lowered or "daily" in lowered:
        schedule_type = "daily"
    elif interval:
        schedule_type = "interval"
        amount = int(interval.group(1))
        payload["interval_minutes"] = amount * (60 if interval.group(2).startswith("hour") else 1)
    elif (weekday := next(
        (
            index
            for index, name in enumerate(
                ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
            )
            if f"every {name}" in lowered
        ),
        -1,
    )) >= 0:
        schedule_type = "weekly"
        payload["schedule_days"] = [weekday]
    elif "every week" in lowered or "weekly" in lowered:
        schedule_type = "weekly"
        payload["schedule_days"] = [local_now.weekday()]

    payload["schedule_type"] = schedule_type
    if schedule_type in {"daily", "weekdays", "weekly"}:
        payload["schedule_time"] = f"{hour:02d}:{minute:02d}"
    elif schedule_type == "one_time":
        day = local_now.date()
        if "tomorrow" in lowered:
            day += timedelta(days=1)
        candidate = datetime.combine(day, time(hour, minute), tzinfo=zone)
        if candidate <= local_now:
            candidate += timedelta(days=1)
        payload["run_at"] = candidate.astimezone(timezone.utc).isoformat()
    return payload
