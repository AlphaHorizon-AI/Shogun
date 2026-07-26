"""Calendar service for CalDAV synchronization."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import caldav
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.email_account import EmailAccount
from shogun.schemas.channels import CalendarEventCreate, CalendarEventResponse
from shogun.services.base_service import BaseService
from shogun.services.comms_permissions import require_comms_permission
from shogun.services.email_service import decrypt_password

_GOOGLE_CALDAV_PREFIX = "https://apidata.googleusercontent.com/caldav/"


def google_caldav_url(email_address: str, calendar_id: str | None = None) -> str:
    """Return Google's supported v2 event-collection URL."""
    identifier = (calendar_id or email_address).strip()
    if identifier.casefold() == "primary":
        identifier = email_address.strip()
    return f"{_GOOGLE_CALDAV_PREFIX}v2/{quote(identifier, safe='')}/events"


def _calendar_url(acc: EmailAccount) -> str:
    credentials = acc.calendar_credentials or {}
    configured = (acc.caldav_url or "").strip()
    if acc.calendar_provider == "google_api" or configured.startswith(_GOOGLE_CALDAV_PREFIX):
        calendar_id = credentials.get("calendar_id") if isinstance(credentials, dict) else None
        return google_caldav_url(acc.email_address, calendar_id)
    return configured


def _dav_client(acc: EmailAccount) -> caldav.DAVClient:
    password = decrypt_password(acc.encrypted_password)
    credentials = acc.calendar_credentials or {}
    access_token = credentials.get("access_token") if isinstance(credentials, dict) else None
    if access_token:
        return caldav.DAVClient(
            url=_calendar_url(acc),
            password=str(access_token),
            auth_type="bearer",
        )
    return caldav.DAVClient(
        url=_calendar_url(acc),
        username=acc.username,
        password=password,
    )


def _calendars(acc: EmailAccount, client: caldav.DAVClient) -> list[caldav.Calendar]:
    if acc.calendar_provider == "google_api" or _calendar_url(acc).startswith(_GOOGLE_CALDAV_PREFIX):
        return [caldav.Calendar(client=client, url=_calendar_url(acc))]
    return client.principal().calendars()


def parse_ical_date(val: str) -> datetime:
    val = val.strip()
    if "T" in val:
        if val.endswith("Z"):
            dt = datetime.strptime(val, "%Y%m%dT%H%M%SZ")
            return dt.replace(tzinfo=timezone.utc)
        else:
            try:
                return datetime.strptime(val, "%Y%m%dT%H%M%S")
            except ValueError:
                # Handle dates with offset or subseconds
                clean_val = val.split("+")[0].split("-")[0]
                return datetime.strptime(clean_val[:15], "%Y%m%dT%H%M%S")
    else:
        dt = datetime.strptime(val[:8], "%Y%m%d")
        return dt.replace(tzinfo=timezone.utc)


def parse_ical(ical_text: str) -> dict[str, Any]:
    """Parse raw iCalendar text into dict."""
    lines = ical_text.replace("\r\n ", "").replace("\r\n\t", "").splitlines()
    data: dict[str, Any] = {
        "location": "",
        "description": "",
        "all_day": False,
    }
    for line in lines:
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key_clean = key.split(";")[0].upper()
        val = val.replace("\\,", ",").replace("\\;", ";").replace("\\N", "\n").replace("\\n", "\n")

        if key_clean == "SUMMARY":
            data["title"] = val
        elif key_clean == "DTSTART":
            data["start"] = parse_ical_date(val)
            if "VALUE=DATE" in key.upper():
                data["all_day"] = True
        elif key_clean == "DTEND":
            data["end"] = parse_ical_date(val)
        elif key_clean == "LOCATION":
            data["location"] = val
        elif key_clean == "DESCRIPTION":
            data["description"] = val
        elif key_clean == "UID":
            data["id"] = val
    return data


class CalendarService(BaseService[EmailAccount]):
    """Handle CalDAV operations governed by ToolGate's Comms policy."""

    def __init__(self, session: AsyncSession):
        super().__init__(EmailAccount, session)

    async def get_account(self) -> EmailAccount | None:
        """Fetch the single calendar account configuration."""
        result = await self.session.execute(select(self.model).limit(1))
        return result.scalars().first()

    async def get_events(self, start_date: datetime, end_date: datetime) -> list[CalendarEventResponse]:
        """Fetch events in a date range via CalDAV and dynamic Bushido schedules."""
        acc = await self.get_account()
        if not acc:
            raise HTTPException(status_code=404, detail="No email/calendar account configured")
        await require_comms_permission("perm_read_calendar")

        # 1. Fetch CalDAV events if configured
        caldav_events = []
        if acc.calendar_provider != "none" and acc.caldav_url:
            def _fetch():
                client = _dav_client(acc)
                calendars = _calendars(acc, client)

                parsed_events = []
                for cal in calendars:
                    events = cal.date_search(start=start_date, end=end_date)
                    for ev in events:
                        try:
                            info = parse_ical(ev.data)
                            if "id" not in info:
                                continue
                            parsed_events.append(CalendarEventResponse(
                                id=info["id"],
                                title=info.get("title", "(No Title)"),
                                start=info["start"],
                                end=info.get("end", info["start"]),
                                location=info.get("location"),
                                description=info.get("description"),
                                all_day=info.get("all_day", False),
                                color=acc.provider,
                            ))
                        except Exception:
                            pass
                return parsed_events

            try:
                caldav_events = await asyncio.to_thread(_fetch)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to fetch CalDAV events: %s", e)

        # 2. Fetch enabled Bushido schedules and calculate occurrences
        cron_events = []
        try:
            from shogun.db.models.bushido import BushidoSchedule
            stmt = select(BushidoSchedule).where(BushidoSchedule.is_enabled.is_(True))
            result = await self.session.execute(stmt)
            schedules = result.scalars().all()

            start_utc = start_date
            if start_utc.tzinfo is None:
                start_utc = start_utc.replace(tzinfo=timezone.utc)
            else:
                start_utc = start_utc.astimezone(timezone.utc)

            end_utc = end_date
            if end_utc.tzinfo is None:
                end_utc = end_utc.replace(tzinfo=timezone.utc)
            else:
                end_utc = end_utc.astimezone(timezone.utc)

            for sched in schedules:
                occs = []
                if sched.frequency == "one-off":
                    if sched.schedule_datetime:
                        try:
                            dt = datetime.fromisoformat(sched.schedule_datetime)
                            if dt.tzinfo is None:
                                dt = dt.replace(tzinfo=timezone.utc)
                            else:
                                dt = dt.astimezone(timezone.utc)
                            if start_utc <= dt <= end_utc:
                                occs.append(dt)
                        except Exception:
                            pass
                elif sched.frequency == "hourly":
                    min_offset = sched.minute_offset or 0
                    curr = start_utc.replace(minute=min_offset, second=0, microsecond=0)
                    if curr < start_utc:
                        curr += timedelta(hours=1)
                    while curr <= end_utc:
                        occs.append(curr)
                        curr += timedelta(hours=1)
                elif sched.frequency == "nightly":
                    hour, minute = 2, 0
                    if sched.schedule_time:
                        try:
                            h_str, m_str = sched.schedule_time.split(":")
                            hour, minute = int(h_str), int(m_str)
                        except Exception:
                            pass
                    curr = start_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if curr < start_utc:
                        curr += timedelta(days=1)
                    while curr <= end_utc:
                        occs.append(curr)
                        curr += timedelta(days=1)
                elif sched.frequency == "weekly":
                    hour, minute = 2, 0
                    if sched.schedule_time:
                        try:
                            h_str, m_str = sched.schedule_time.split(":")
                            hour, minute = int(h_str), int(m_str)
                        except Exception:
                            pass
                    days_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
                    active_wdays = []
                    if sched.schedule_days:
                        for d in sched.schedule_days:
                            d_clean = d.lower()[:3]
                            if d_clean in days_map:
                                active_wdays.append(days_map[d_clean])
                    if not active_wdays:
                        active_wdays = [0, 2, 4]
                    curr = start_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if curr < start_utc:
                        curr += timedelta(days=1)
                    while curr <= end_utc:
                        if curr.weekday() in active_wdays:
                            occs.append(curr)
                        curr += timedelta(days=1)
                elif sched.frequency == "monthly":
                    hour, minute = 2, 0
                    if sched.schedule_time:
                        try:
                            h_str, m_str = sched.schedule_time.split(":")
                            hour, minute = int(h_str), int(m_str)
                        except Exception:
                            pass
                    target_day = sched.schedule_day or 1
                    curr = start_utc.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if curr < start_utc:
                        curr += timedelta(days=1)
                    while curr <= end_utc:
                        if curr.day == target_day:
                            occs.append(curr)
                        curr += timedelta(days=1)

                for occ in occs:
                    cron_events.append(CalendarEventResponse(
                        id=f"cron_{sched.id}_{occ.strftime('%Y%m%dT%H%M%SZ')}",
                        title=f"🤖 Cron: {sched.name}",
                        start=occ,
                        end=occ + timedelta(minutes=30),
                        location="Shogun Operations",
                        description=(
                            f"Job Type: {sched.job_type}\nFrequency: {sched.frequency}\n"
                            f"Instruction: {sched.task_instruction or 'None'}"
                        ),
                        all_day=False,
                        color="cron_job",
                    ))
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Failed to construct cron events: %s", e)

        return caldav_events + cron_events

    async def create_event(self, data: CalendarEventCreate) -> CalendarEventResponse:
        """Create an event via CalDAV."""
        acc = await self.get_account()
        if not acc:
            raise HTTPException(status_code=404, detail="No email/calendar account configured")
        await require_comms_permission("perm_create_events")
        if acc.calendar_provider == "none" or not acc.caldav_url:
            raise HTTPException(status_code=400, detail="Calendar integration is not configured or enabled")

        uid = str(uuid.uuid4())

        def _create():
            client = _dav_client(acc)
            calendars = _calendars(acc, client)
            if not calendars:
                raise Exception("No calendars found on the server.")

            calendar = calendars[0]  # default to first calendar

            dtstamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            start_str = data.start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            end_str = data.end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

            event_ical = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Shogun//NONSGML Calendar//EN
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{dtstamp_str}
SUMMARY:{data.title}
DTSTART:{start_str}
DTEND:{end_str}
DESCRIPTION:{data.description or ""}
LOCATION:{data.location or ""}
END:VEVENT
END:VCALENDAR"""

            calendar.add_event(event_ical)
            return CalendarEventResponse(
                id=uid,
                title=data.title,
                start=data.start,
                end=data.end,
                location=data.location,
                description=data.description,
                all_day=data.all_day,
                color=acc.provider,
            )

        try:
            return await asyncio.to_thread(_create)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create event: {str(e)}")

    async def update_event(self, event_id: str, data: CalendarEventCreate) -> CalendarEventResponse:
        """Update an event by deleting and re-creating it with the same ID."""
        if event_id.startswith("cron_"):
            raise HTTPException(
                status_code=400,
                detail="Cannot edit system cron job events from the calendar. Manage them from Operations.",
            )
        acc = await self.get_account()
        if not acc:
            raise HTTPException(status_code=404, detail="No email/calendar account configured")
        await require_comms_permission("perm_edit_events")
        if acc.calendar_provider == "none" or not acc.caldav_url:
            raise HTTPException(status_code=400, detail="Calendar integration is not configured or enabled")

        def _update():
            client = _dav_client(acc)
            calendars = _calendars(acc, client)

            # Delete existing
            deleted = False
            for cal in calendars:
                try:
                    ev = cal.event_by_uid(event_id)
                    ev.delete()
                    deleted = True
                    break
                except Exception:
                    pass

            if not deleted:
                raise Exception("Event to update was not found.")

            # Create new with same ID
            calendar = calendars[0]
            dtstamp_str = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            start_str = data.start.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            end_str = data.end.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

            event_ical = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Shogun//NONSGML Calendar//EN
BEGIN:VEVENT
UID:{event_id}
DTSTAMP:{dtstamp_str}
SUMMARY:{data.title}
DTSTART:{start_str}
DTEND:{end_str}
DESCRIPTION:{data.description or ""}
LOCATION:{data.location or ""}
END:VEVENT
END:VCALENDAR"""

            calendar.add_event(event_ical)
            return CalendarEventResponse(
                id=event_id,
                title=data.title,
                start=data.start,
                end=data.end,
                location=data.location,
                description=data.description,
                all_day=data.all_day,
                color=acc.provider,
            )

        try:
            return await asyncio.to_thread(_update)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update event: {str(e)}")

    async def delete_event(self, event_id: str) -> dict[str, Any]:
        """Delete an event via CalDAV."""
        if event_id.startswith("cron_"):
            raise HTTPException(
                status_code=400,
                detail="Cannot delete system cron job events from the calendar. Manage them from Operations.",
            )
        acc = await self.get_account()
        if not acc:
            raise HTTPException(status_code=404, detail="No email/calendar account configured")
        await require_comms_permission("perm_delete_events")
        if acc.calendar_provider == "none" or not acc.caldav_url:
            raise HTTPException(status_code=400, detail="Calendar integration is not configured or enabled")

        def _delete():
            client = _dav_client(acc)
            calendars = _calendars(acc, client)

            deleted = False
            for cal in calendars:
                try:
                    ev = cal.event_by_uid(event_id)
                    ev.delete()
                    deleted = True
                    break
                except Exception:
                    pass

            if not deleted:
                raise Exception("Event was not found or could not be deleted.")
            return {"ok": True, "message": "Event deleted successfully."}

        try:
            return await asyncio.to_thread(_delete)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete event: {str(e)}")
