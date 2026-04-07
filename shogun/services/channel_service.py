"""Channel service — Telegram integration stub."""

from __future__ import annotations


class ChannelService:
    """Telegram and future channel integrations. Stub for Phase 1."""

    async def get_telegram_status(self) -> dict:
        return {
            "connected": False,
            "bot_username": None,
            "mode": None,
            "last_message_at": None,
        }

    async def connect_telegram(self, bot_token: str, mode: str = "polling") -> dict:
        # Phase 2: actual Telegram bot connection
        return {"connected": False, "message": "Telegram integration not yet implemented"}
