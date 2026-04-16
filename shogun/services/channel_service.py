"""Channel service — Telegram integration with real bot validation."""

from __future__ import annotations

import httpx


_TELEGRAM_KEY = "telegram_config"


async def _get_agent_bushido() -> dict:
    """Read the primary Shogun agent's bushido_settings."""
    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent
    from sqlalchemy import select

    async with async_session_factory() as db:
        result = await db.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            ).limit(1)
        )
        agent = result.scalar_one_or_none()
        return dict(agent.bushido_settings or {}) if agent else {}


async def _save_agent_bushido(settings: dict) -> None:
    """Write back the primary Shogun agent's bushido_settings."""
    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent
    from sqlalchemy import select

    async with async_session_factory() as db:
        result = await db.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            ).limit(1)
        )
        agent = result.scalar_one_or_none()
        if not agent:
            return
        agent.bushido_settings = {**dict(agent.bushido_settings or {}), **settings}
        await db.commit()


class ChannelService:
    """Telegram and future channel integrations."""

    # ── Status ────────────────────────────────────────────────────────

    async def get_telegram_status(self) -> dict:
        bushido = await _get_agent_bushido()
        cfg = bushido.get(_TELEGRAM_KEY, {})
        return {
            "connected": cfg.get("connected", False),
            "bot_username": cfg.get("bot_username"),
            "bot_id": cfg.get("bot_id"),
            "first_name": cfg.get("first_name"),
            "mode": cfg.get("mode", "polling"),
            "allowed_chat_ids": cfg.get("allowed_chat_ids", []),
            "webhook_url": cfg.get("webhook_url"),
            "last_connected_at": cfg.get("last_connected_at"),
        }

    # ── Connect ───────────────────────────────────────────────────────

    async def connect_telegram(
        self,
        bot_token: str,
        mode: str = "polling",
        allowed_chat_ids: list[str] | None = None,
        webhook_url: str | None = None,
    ) -> dict:
        """Validate the bot token with the Telegram API and persist config."""
        from datetime import datetime, timezone

        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
        except httpx.ConnectError:
            return {"connected": False, "error": "Cannot reach api.telegram.org — check network."}
        except httpx.TimeoutException:
            return {"connected": False, "error": "Telegram API timed out."}

        if not resp.is_success:
            data = resp.json()
            return {
                "connected": False,
                "error": data.get("description", f"HTTP {resp.status_code}"),
            }

        bot = resp.json().get("result", {})
        cfg = {
            "bot_token": bot_token,
            "connected": True,
            "bot_username": bot.get("username"),
            "bot_id": bot.get("id"),
            "first_name": bot.get("first_name"),
            "mode": mode,
            "allowed_chat_ids": allowed_chat_ids or [],
            "webhook_url": webhook_url,
            "last_connected_at": datetime.now(timezone.utc).isoformat(),
        }
        bushido = await _get_agent_bushido()
        bushido[_TELEGRAM_KEY] = cfg
        await _save_agent_bushido(bushido)
        return {k: v for k, v in cfg.items() if k != "bot_token"}  # never expose token in response

    # ── Test message ──────────────────────────────────────────────────

    async def test_message(self, chat_id: str) -> dict:
        """Send a test message to the given chat ID."""
        bushido = await _get_agent_bushido()
        cfg = bushido.get(_TELEGRAM_KEY, {})
        bot_token = cfg.get("bot_token")
        if not bot_token:
            return {"ok": False, "error": "No bot token configured."}

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json={
                    "chat_id": chat_id,
                    "text": "⚙️ *Shogun Test Message*\n\nTelegram connection is working correctly. This is an automated test from the Katana control panel.",
                    "parse_mode": "Markdown",
                })
        except Exception as e:
            return {"ok": False, "error": str(e)}

        if resp.is_success:
            return {"ok": True, "message": f"Test message sent to {chat_id}."}
        data = resp.json()
        return {"ok": False, "error": data.get("description", f"HTTP {resp.status_code}")}

    # ── Disconnect ────────────────────────────────────────────────────

    async def disconnect_telegram(self) -> dict:
        bushido = await _get_agent_bushido()
        bushido.pop(_TELEGRAM_KEY, None)
        await _save_agent_bushido(bushido)
        return {"disconnected": True}
