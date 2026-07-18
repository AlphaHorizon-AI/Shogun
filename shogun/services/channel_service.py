"""Channel service — Telegram integration with real bot validation."""

from __future__ import annotations

import httpx

_TELEGRAM_KEY = "telegram_config"


async def _get_agent_bushido() -> dict:
    """Read the primary Shogun agent's bushido_settings."""
    from sqlalchemy import select

    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent

    async with async_session_factory() as db:
        result = await db.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary.is_(True),
                Agent.is_deleted.is_(False),
            ).limit(1)
        )
        agent = result.scalar_one_or_none()
        return dict(agent.bushido_settings or {}) if agent else {}


async def _save_agent_bushido(settings: dict) -> None:
    """Write back the primary Shogun agent's bushido_settings."""
    from sqlalchemy import select

    from shogun.db.engine import async_session_factory
    from shogun.db.models.agent import Agent

    async with async_session_factory() as db:
        result = await db.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary.is_(True),
                Agent.is_deleted.is_(False),
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
        try:
            from shogun.services.telegram_poller import get_telegram_poller_health

            poller = get_telegram_poller_health()
        except ImportError:
            poller = {"running": False, "last_error": "Telegram poller is unavailable."}
        return {
            "connected": cfg.get("connected", False),
            "bot_username": cfg.get("bot_username"),
            "bot_id": cfg.get("bot_id"),
            "first_name": cfg.get("first_name"),
            "mode": cfg.get("mode", "polling"),
            "allowed_chat_ids": cfg.get("allowed_chat_ids", []),
            "webhook_url": cfg.get("webhook_url"),
            "last_connected_at": cfg.get("last_connected_at"),
            "can_join_groups": cfg.get("can_join_groups"),
            "can_read_all_group_messages": cfg.get("can_read_all_group_messages"),
            "poller": poller,
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

        bot_token = bot_token.strip()
        mode = (mode or "polling").strip().lower()
        url = f"https://api.telegram.org/bot{bot_token}/getMe"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                if resp.is_success and mode == "polling":
                    webhook_resp = await client.post(
                        f"https://api.telegram.org/bot{bot_token}/deleteWebhook",
                        json={"drop_pending_updates": False},
                    )
                    if not webhook_resp.is_success or not webhook_resp.json().get("ok"):
                        return {
                            "connected": False,
                            "error": "Telegram webhook could not be removed, so inbound polling cannot start.",
                        }
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
            "can_join_groups": bot.get("can_join_groups"),
            "can_read_all_group_messages": bot.get("can_read_all_group_messages"),
            "mode": mode,
            "allowed_chat_ids": allowed_chat_ids or [],
            "webhook_url": webhook_url,
            "last_connected_at": datetime.now(timezone.utc).isoformat(),
        }
        bushido = await _get_agent_bushido()
        bushido[_TELEGRAM_KEY] = cfg
        await _save_agent_bushido(bushido)

        # Invalidate the poller's config cache so it picks up the new token immediately
        try:
            from shogun.services.telegram_poller import invalidate_telegram_config_cache
            invalidate_telegram_config_cache()
        except ImportError:
            pass

        return {k: v for k, v in cfg.items() if k != "bot_token"}  # never expose token in response

    async def diagnose_telegram(self) -> dict:
        """Check the remote delivery mode, privacy capability, and local poller."""
        bushido = await _get_agent_bushido()
        cfg = bushido.get(_TELEGRAM_KEY, {})
        bot_token = cfg.get("bot_token")
        if not bot_token:
            return {
                "inbound_ready": False,
                "issues": ["Telegram is not connected."],
                "poller": {"running": False},
            }

        from shogun.services.telegram_poller import get_telegram_poller_health

        issues: list[str] = []
        warnings: list[str] = []
        remote: dict = {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                me_response = await client.get(f"https://api.telegram.org/bot{bot_token}/getMe")
                webhook_response = await client.get(f"https://api.telegram.org/bot{bot_token}/getWebhookInfo")
            if me_response.is_success:
                me = me_response.json().get("result", {})
                remote.update(
                    {
                        "bot_username": me.get("username"),
                        "can_join_groups": me.get("can_join_groups"),
                        "can_read_all_group_messages": me.get("can_read_all_group_messages"),
                    }
                )
                if me.get("can_read_all_group_messages") is False:
                    warnings.append(
                        "Telegram privacy mode is enabled. Disable it with BotFather /setprivacy, "
                        "or keep the bot as a group administrator."
                    )
            else:
                issues.append(f"Telegram getMe failed with HTTP {me_response.status_code}.")

            if webhook_response.is_success:
                webhook = webhook_response.json().get("result", {})
                remote.update(
                    {
                        "webhook_url": webhook.get("url") or "",
                        "pending_update_count": webhook.get("pending_update_count", 0),
                        "last_webhook_error": webhook.get("last_error_message"),
                    }
                )
                if cfg.get("mode", "polling") == "polling" and webhook.get("url"):
                    issues.append("A Telegram webhook is active and blocks Shogun's polling listener.")
            else:
                issues.append(f"Telegram getWebhookInfo failed with HTTP {webhook_response.status_code}.")
        except Exception as exc:
            issues.append(f"Telegram diagnostics request failed: {exc}")

        poller = get_telegram_poller_health()
        if not poller.get("running"):
            issues.append("The local Telegram polling task is not running.")
        if poller.get("last_error"):
            issues.append(str(poller["last_error"]))

        return {
            "inbound_ready": not issues,
            "mode": cfg.get("mode", "polling"),
            "allowed_chat_ids": cfg.get("allowed_chat_ids", []),
            "remote": remote,
            "poller": poller,
            "issues": list(dict.fromkeys(issues)),
            "warnings": list(dict.fromkeys(warnings)),
        }

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
                    "text": (
                        "⚙️ *Shogun Test Message*\n\nTelegram connection is working correctly. "
                        "This is an automated test from the Katana control panel."
                    ),
                    "parse_mode": "Markdown",
                })
        except Exception as e:
            return {"ok": False, "error": str(e)}

        if resp.is_success:
            return {"ok": True, "message": f"Test message sent to {chat_id}."}
        data = resp.json()
        return {"ok": False, "error": data.get("description", f"HTTP {resp.status_code}")}

    # ── Auto-Detect Chat ID ──────────────────────────────────────────

    async def detect_chat_id(self) -> dict:
        """Poll the getUpdates endpoint to automatically detect the user's Chat ID."""
        bushido = await _get_agent_bushido()
        cfg = bushido.get(_TELEGRAM_KEY, {})
        bot_token = cfg.get("bot_token")
        if not bot_token:
            return {"ok": False, "error": "No bot token configured. Connect your bot first!"}

        url = f"https://api.telegram.org/bot{bot_token}/getUpdates?offset=-1"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
        except Exception as e:
            return {"ok": False, "error": f"Network error: {str(e)}"}

        if not resp.is_success:
            data = resp.json()
            return {"ok": False, "error": data.get("description", f"HTTP {resp.status_code}")}

        result_arr = resp.json().get("result", [])
        if not result_arr:
            return {
                "ok": False,
                "error": (
                    "No messages found. Please send a message (like 'Hello') to your bot on Telegram first, "
                    "then try again."
                ),
            }

        # Extract the most recent message
        latest_update = result_arr[-1]
        msg = latest_update.get("message") or latest_update.get("my_chat_member")
        if not msg:
            return {"ok": False, "error": "Could not parse message data from Telegram."}

        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        title_or_name = chat.get("first_name") or chat.get("title") or "Unknown"

        if not chat_id:
             return {"ok": False, "error": "Could not extract Chat ID from update."}

        return {"ok": True, "chat_id": str(chat_id), "name": title_or_name}

    # ── Disconnect ────────────────────────────────────────────────────

    async def disconnect_telegram(self) -> dict:
        bushido = await _get_agent_bushido()
        bushido.pop(_TELEGRAM_KEY, None)
        await _save_agent_bushido(bushido)

        # Invalidate the poller's config cache so it stops polling immediately
        try:
            from shogun.services.telegram_poller import invalidate_telegram_config_cache
            invalidate_telegram_config_cache()
        except ImportError:
            pass

        return {"disconnected": True}
