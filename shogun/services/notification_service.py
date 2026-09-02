"""Operator-visible notifications and outbound Telegram delivery."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger("shogun.notifications")

_notifications: deque[dict[str, Any]] = deque(maxlen=200)
_TELEGRAM_TEXT_LIMIT = 4096


def publish_notification(
    *,
    event_type: str,
    title: str,
    message: str,
    severity: str = "warning",
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish an in-app notification retained for the current server process."""
    item = {
        "id": uuid.uuid4().hex,
        "event_type": event_type,
        "title": title,
        "message": message,
        "severity": severity,
        "detail": detail or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _notifications.append(item)
    return item


def list_notifications(after: str | None = None) -> list[dict[str, Any]]:
    items = list(_notifications)
    if not after:
        return items[-20:]
    for index, item in enumerate(items):
        if item["id"] == after:
            return items[index + 1 :]
    return items[-20:]


async def send_channel_message(
    message: str,
    *,
    channel: str = "both",
    telegram_chat_ids: list[str] | None = None,
    telegram_message_thread_id: int | None = None,
    teams_conversation_ids: list[str] | None = None,
    event_type: str = "agentflow.message",
) -> dict[str, Any]:
    """Send a plain-text message to Yellow Label's Telegram channel."""
    from shogun.services.harakiri_runtime import harakiri_latch_active

    if channel == "teams":
        return {
            "teams": {
                "ok": False,
                "error": "Microsoft Teams is not available in Yellow Label",
                "sent": 0,
            }
        }
    if channel == "both":
        channel = "telegram"

    if harakiri_latch_active():
        blocked = {"ok": False, "error": "HARAKIRI is active", "sent": 0, "blocked": True}
        return {
            name: dict(blocked)
            for name in ("telegram", "teams")
            if channel in {name, "both"}
        }
    results: dict[str, Any] = {}
    if channel in {"telegram", "both"}:
        results["telegram"] = await _send_telegram(
            message,
            telegram_chat_ids,
            message_thread_id=telegram_message_thread_id,
        )
    return results


def _apply_telegram_message_thread(
    payload: dict[str, Any],
    message_thread_id: int | None,
) -> dict[str, Any]:
    """Attach a forum topic to any Telegram API payload when one is requested."""
    if message_thread_id is not None:
        payload["message_thread_id"] = int(message_thread_id)
    return payload


def _split_telegram_message(message: str, limit: int = _TELEGRAM_TEXT_LIMIT) -> list[str]:
    """Split text on readable boundaries without exceeding Telegram's limit."""
    if len(message) <= limit:
        return [message]

    chunks: list[str] = []
    remaining = message
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break

        window = remaining[:limit]
        split_at = max(window.rfind("\n\n"), window.rfind("\n"), window.rfind(" "))
        if split_at < limit // 2:
            split_at = limit

        chunk = remaining[:split_at].rstrip()
        if not chunk:
            chunk = remaining[:limit]
            split_at = limit
        chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()
    return chunks


def _telegram_api_error(response: httpx.Response) -> str:
    """Return Telegram's useful error description without exposing credentials."""
    description = ""
    try:
        data = response.json()
        if isinstance(data, dict):
            description = str(data.get("description") or "").strip()
    except (ValueError, TypeError):
        description = ""
    return (
        f"HTTP {response.status_code}: {description}"
        if description
        else f"HTTP {response.status_code}"
    )


async def _send_telegram(
    message: str,
    chat_ids: list[str] | None,
    *,
    message_thread_id: int | None = None,
) -> dict[str, Any]:
    from shogun.services.channel_service import _get_agent_bushido
    from shogun.services.harakiri_runtime import harakiri_latch_active

    if harakiri_latch_active():
        return {"ok": False, "error": "HARAKIRI is active", "sent": 0, "blocked": True}

    config = (await _get_agent_bushido()).get("telegram_config", {})
    token = config.get("bot_token")
    targets = [str(x) for x in (chat_ids or config.get("allowed_chat_ids") or []) if str(x)]
    if not token or not config.get("connected"):
        return {"ok": False, "error": "Telegram is not connected", "sent": 0}
    if not targets:
        return {"ok": False, "error": "No Telegram chat IDs configured", "sent": 0}

    sent = 0
    errors: list[str] = []
    chunks = _split_telegram_message(message)
    async with httpx.AsyncClient(timeout=10.0) as client:
        for target in targets:
            if harakiri_latch_active():
                errors.append(f"{target}: blocked by HARAKIRI")
                continue
            parts = target.split(":")
            chat_id = parts[0]
            target_thread_id = message_thread_id
            if len(parts) > 1:
                try:
                    target_thread_id = int(parts[1])
                except ValueError:
                    pass

            target_delivered = True
            for part_number, chunk in enumerate(chunks, start=1):
                payload = _apply_telegram_message_thread(
                    {"chat_id": chat_id, "text": chunk},
                    target_thread_id,
                )
                part_label = (
                    target
                    if len(chunks) == 1
                    else f"{target} part {part_number}/{len(chunks)}"
                )

                try:
                    response = await client.post(
                        f"https://api.telegram.org/bot{token}/sendMessage",
                        json=payload,
                    )
                    if not response.is_success:
                        errors.append(f"{part_label}: {_telegram_api_error(response)}")
                        target_delivered = False
                        break
                except Exception as exc:
                    errors.append(f"{part_label}: {exc}")
                    target_delivered = False
                    break
            if target_delivered:
                sent += 1
    return {
        "ok": sent == len(targets),
        "sent": sent,
        "errors": errors,
        "parts_per_target": len(chunks),
    }


async def notify_model_fallback(
    *,
    from_model: str,
    to_model: str,
    reason: str,
    context: str,
    timeout_seconds: int,
) -> None:
    """Create every required transparency signal for a model fallback."""
    message = (
        f"MODEL FALLBACK: {context} switched from '{from_model}' to '{to_model}'. "
        f"Reason: {reason}. Per-attempt timeout: {timeout_seconds}s."
    )
    logger.warning(message)
    detail = {
        "from_model": from_model,
        "to_model": to_model,
        "reason": reason,
        "context": context,
        "timeout_seconds": timeout_seconds,
    }
    publish_notification(
        event_type="model.fallback",
        title="Model fallback activated",
        message=message,
        severity="warning",
        detail=detail,
    )

    from shogun.services.event_logger import EventLogger

    await EventLogger.emit_model_event(
        "model.fallback",
        message,
        model_used=to_model,
        provider_used=None,
        severity="warning",
        detail=detail,
    )
    # External delivery must never delay the fallback model invocation.
    asyncio.create_task(_deliver_fallback_channels(message))


async def _deliver_fallback_channels(message: str) -> None:
    """Deliver fallback alerts in the background and surface delivery failures."""
    try:
        results = await send_channel_message(
            f"⚠️ {message}",
            channel="both",
            event_type="model.fallback",
        )
        for channel, result in results.items():
            if not result.get("ok"):
                logger.warning("Fallback %s notification was not delivered: %s", channel, result)
    except Exception:
        logger.exception("Fallback channel notification delivery crashed")
