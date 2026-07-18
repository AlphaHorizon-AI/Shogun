"""Channel schemas — Telegram and future communication integrations."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from shogun.schemas.common import ShogunBase


class TelegramConnectRequest(ShogunBase):
    """Request body for connecting the Telegram bot."""

    bot_token: str
    mode: str = "polling"
    allowed_chat_ids: list[str] | None = None
    webhook_url: str | None = None


class TelegramSettingsUpdate(ShogunBase):
    """Request body for updating Telegram settings."""

    mode: str | None = None
    allowed_chat_ids: list[str] | None = None
    webhook_url: str | None = None


class TelegramStatusResponse(ShogunBase):
    """Response model for Telegram connection status."""

    connected: bool = False
    bot_username: str | None = None
    bot_id: int | None = None
    first_name: str | None = None
    mode: str | None = None
    allowed_chat_ids: list[str] = []
    webhook_url: str | None = None
    last_connected_at: str | None = None
    can_join_groups: bool | None = None
    can_read_all_group_messages: bool | None = None
    poller: dict[str, Any] = {}


class EmailAccountCreate(ShogunBase):
    provider: str  # 'gmail', 'outlook', 'proton', 'other'
    display_name: str | None = None
    email_address: str
    protocol: str = "imap"
    imap_host: str
    imap_port: int
    imap_use_ssl: bool = True
    smtp_host: str
    smtp_port: int
    smtp_use_ssl: bool = True
    username: str
    password: str
    caldav_url: str | None = None
    calendar_provider: str = "none"
    calendar_credentials: dict[str, Any] | None = None


class EmailAccountUpdate(ShogunBase):
    provider: str | None = None
    display_name: str | None = None
    email_address: str | None = None
    protocol: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_use_ssl: bool | None = None
    smtp_host: str | None = None
    smtp_port: int | None = None
    smtp_use_ssl: bool | None = None
    username: str | None = None
    password: str | None = None
    caldav_url: str | None = None
    calendar_provider: str | None = None
    calendar_credentials: dict[str, Any] | None = None
    is_active: bool | None = None

    # Permission toggles
    perm_read_mail: bool | None = None
    perm_send_mail: bool | None = None
    perm_delete_mail: bool | None = None
    perm_read_calendar: bool | None = None
    perm_create_events: bool | None = None
    perm_edit_events: bool | None = None
    perm_delete_events: bool | None = None


class EmailAccountPermissionsUpdate(ShogunBase):
    perm_read_mail: bool
    perm_send_mail: bool
    perm_delete_mail: bool
    perm_read_calendar: bool
    perm_create_events: bool
    perm_edit_events: bool
    perm_delete_events: bool


class EmailAccountResponse(ShogunBase):
    id: uuid.UUID
    provider: str
    display_name: str | None = None
    email_address: str
    protocol: str
    imap_host: str
    imap_port: int
    imap_use_ssl: bool
    smtp_host: str
    smtp_port: int
    smtp_use_ssl: bool
    username: str
    caldav_url: str | None = None
    calendar_provider: str
    calendar_credentials: dict[str, Any] | None = None
    is_active: bool
    last_sync_at: datetime | None = None

    perm_read_mail: bool
    perm_send_mail: bool
    perm_delete_mail: bool
    perm_read_calendar: bool
    perm_create_events: bool
    perm_edit_events: bool
    perm_delete_events: bool


class EmailTestResponse(ShogunBase):
    ok: bool
    imap_ok: bool
    smtp_ok: bool
    message: str | None = None


class EmailMessageSummary(ShogunBase):
    uid: str
    from_address: str
    to_address: str
    subject: str
    date: str
    body_preview: str
    is_read: bool
    has_attachments: bool


class EmailMessageFull(EmailMessageSummary):
    body_html: str | None = None
    body_text: str | None = None
    attachments: list[dict[str, Any]] = []


class EmailComposeRequest(ShogunBase):
    to_address: str
    cc_address: str | None = None
    bcc_address: str | None = None
    subject: str
    body: str
    reply_to_uid: str | None = None


class CalendarEventResponse(ShogunBase):
    id: str
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None
    all_day: bool = False
    color: str | None = None


class CalendarEventCreate(ShogunBase):
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None
    all_day: bool = False

