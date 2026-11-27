"""In-memory UI notifications plus optional Telegram channel delivery for AgentFlow."""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections import deque
from typing import Any

import httpx

log = logging.getLogger("shogun.notifications")

_NOTIFICATIONS: deque[dict[str, Any]] = deque(maxlen=50)


def push_notification(
    title: str,
    message: str,
    *,
    severity: str = "warning",
    category: str = "model_router",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item = {
        "id": str(uuid.uuid4()),
        "title": title,
        "message": message,
        "severity": severity,
        "category": category,
        "details": details or {},
        "created_at": time.time(),
    }
    _NOTIFICATIONS.append(item)
    return item


def list_notifications(after: str | None = None) -> list[dict[str, Any]]:
    items = list(_NOTIFICATIONS)
    if not after:
        return items[-10:]
    for idx, item in enumerate(items):
        if item["id"] == after:
            return items[idx + 1 :]
    return []


async def notify_model_fallback(
    *,
    from_model: str,
    from_provider: str,
    to_model: str,
    to_provider: str,
    reason: str,
    profile_name: str | None = None,
) -> dict[str, Any]:
    title = "Model fallback used"
    profile_label = f" ({profile_name})" if profile_name else ""
    message = (
        f"Switched from {from_model} ({from_provider}) to {to_model} ({to_provider})"
        f"{profile_label}: {reason}"
    )
    log.warning("%s — %s", title, message)
    return push_notification(
        title,
        message,
        severity="warning",
        category="model_fallback",
        details={
            "from_model": from_model,
            "from_provider": from_provider,
            "to_model": to_model,
            "to_provider": to_provider,
            "reason": reason,
            "profile_name": profile_name,
        },
    )


async def send_channel_message(
    message: str,
    *,
    channel: str = "telegram",
    telegram_chat_ids: list[str] | None = None,
    telegram_message_thread_id: int | None = None,
) -> dict[str, Any]:
    """Send a message to Telegram using optional TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID in .env."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_ids = telegram_chat_ids or [
        cid.strip() for cid in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if cid.strip()
    ]
    if not bot_token or not chat_ids:
        return {
            channel: {
                "ok": False,
                "error": (
                    "Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env "
                    "(or pass chat_id on the node)."
                ),
            }
        }
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=20.0) as client:
        for cid in chat_ids:
            payload: dict[str, Any] = {"chat_id": cid, "text": message[:4096]}
            if telegram_message_thread_id is not None:
                payload["message_thread_id"] = telegram_message_thread_id
            try:
                resp = await client.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json=payload)
                resp.raise_for_status()
            except Exception as exc:
                errors.append(f"{cid}: {exc}")
    if errors:
        return {channel: {"ok": False, "errors": errors}}
    return {channel: {"ok": True}}
