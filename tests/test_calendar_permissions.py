"""Calendar provider and centralized Comms permission regressions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest


def _account(**overrides):
    values = {
        "calendar_provider": "google_api",
        "calendar_credentials": None,
        "caldav_url": "https://apidata.googleusercontent.com/caldav/v1/calendars/primary/events",
        "email_address": "operator+calendar@example.com",
        "username": "operator+calendar@example.com",
        "encrypted_password": "encrypted",
        "provider": "gmail",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_google_caldav_legacy_url_is_normalized_to_v2_calendar_id():
    from shogun.services.calendar_service import _calendar_url, google_caldav_url

    expected = "https://apidata.googleusercontent.com/caldav/v2/operator%2Bcalendar%40example.com/events"
    assert google_caldav_url("operator+calendar@example.com", "primary") == expected
    assert _calendar_url(_account()) == expected


def test_google_caldav_uses_bearer_token_when_configured(monkeypatch):
    import shogun.services.calendar_service as calendar_service

    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(calendar_service, "decrypt_password", lambda _value: "mail-password")
    monkeypatch.setattr(calendar_service.caldav, "DAVClient", fake_client)
    calendar_service._dav_client(_account(calendar_credentials={"access_token": "oauth-token"}))

    assert captured["auth_type"] == "bearer"
    assert captured["password"] == "oauth-token"
    assert captured["url"].endswith("operator%2Bcalendar%40example.com/events")
    assert "username" not in captured


@pytest.mark.asyncio
async def test_account_permissions_come_only_from_toolgate_comms(monkeypatch):
    from shogun.api import security
    from shogun.services.comms_permissions import effective_account_permissions

    async def posture():
        return {
            "comms_read_email": True,
            "comms_send_email": False,
            "comms_read_calendar": True,
            "comms_create_events": False,
        }

    monkeypatch.setattr(security, "_get_agent_posture", posture)
    permissions = await effective_account_permissions()
    assert permissions == {
        "perm_read_mail": True,
        "perm_send_mail": False,
        "perm_delete_mail": False,
        "perm_read_calendar": True,
        "perm_create_events": False,
        "perm_edit_events": False,
        "perm_delete_events": False,
    }


@pytest.mark.asyncio
async def test_google_create_writes_to_normalized_event_collection(monkeypatch):
    import shogun.services.calendar_service as calendar_service
    from shogun.schemas.channels import CalendarEventCreate

    account = _account()
    written = []
    checked = []
    service = calendar_service.CalendarService(SimpleNamespace())

    async def get_account():
        return account

    async def require(permission):
        checked.append(permission)

    class FakeCalendar:
        def add_event(self, payload):
            written.append(payload)

    monkeypatch.setattr(service, "get_account", get_account)
    monkeypatch.setattr(calendar_service, "require_comms_permission", require)
    monkeypatch.setattr(calendar_service, "_dav_client", lambda _account: SimpleNamespace())
    monkeypatch.setattr(calendar_service, "_calendars", lambda _account, _client: [FakeCalendar()])

    start = datetime(2026, 7, 27, 8, 0, tzinfo=timezone.utc)
    result = await service.create_event(CalendarEventCreate(
        title="Morning brief",
        start=start,
        end=start + timedelta(minutes=30),
    ))

    assert checked == ["perm_create_events"]
    assert result.title == "Morning brief"
    assert "SUMMARY:Morning brief" in written[0]
