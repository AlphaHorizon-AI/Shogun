"""Channel schemas — Telegram and future communication integrations."""

from __future__ import annotations

from shogun.schemas.common import ShogunBase


class TelegramConnectRequest(ShogunBase):
    """Request body for connecting the Telegram bot."""

    bot_token: str
    mode: str = "polling"


class TelegramSettingsUpdate(ShogunBase):
    """Request body for updating Telegram settings."""

    mode: str | None = None
    allowed_chat_ids: list[str] | None = None


class TelegramStatusResponse(ShogunBase):
    """Response model for Telegram connection status."""

    connected: bool = False
    bot_username: str | None = None
    mode: str | None = None
    last_message_at: str | None = None
