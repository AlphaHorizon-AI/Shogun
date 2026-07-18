"""Operator-visible notifications and outbound Telegram/Teams delivery."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select

from shogun.config import settings

logger = logging.getLogger("shogun.notifications")

_notifications: deque[dict[str, Any]] = deque(maxlen=200)


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
    """Send a plain-text message to configured operator channels."""
    results: dict[str, Any] = {}
    if channel in {"telegram", "both"}:
        results["telegram"] = await _send_telegram(
            message,
            telegram_chat_ids,
            message_thread_id=telegram_message_thread_id,
        )
    if channel in {"teams", "both"}:
        results["teams"] = await _send_teams(message, teams_conversation_ids, event_type)
    return results


def _apply_telegram_message_thread(
    payload: dict[str, Any],
    message_thread_id: int | None,
) -> dict[str, Any]:
    """Attach a forum topic to any Telegram API payload when one is requested."""
    if message_thread_id is not None:
        payload["message_thread_id"] = int(message_thread_id)
    return payload


async def _send_telegram(
    message: str,
    chat_ids: list[str] | None,
    *,
    message_thread_id: int | None = None,
) -> dict[str, Any]:
    from shogun.services.channel_service import _get_agent_bushido

    config = (await _get_agent_bushido()).get("telegram_config", {})
    token = config.get("bot_token")
    targets = [str(x) for x in (chat_ids or config.get("allowed_chat_ids") or []) if str(x)]
    if not token or not config.get("connected"):
        return {"ok": False, "error": "Telegram is not connected", "sent": 0}
    if not targets:
        return {"ok": False, "error": "No Telegram chat IDs configured", "sent": 0}

    sent = 0
    errors: list[str] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for target in targets:
            parts = target.split(":")
            chat_id = parts[0]
            target_thread_id = message_thread_id
            if len(parts) > 1:
                try:
                    target_thread_id = int(parts[1])
                except ValueError:
                    pass

            payload = _apply_telegram_message_thread(
                {"chat_id": chat_id, "text": message},
                target_thread_id,
            )

            try:
                response = await client.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json=payload,
                )
                if response.is_success:
                    sent += 1
                else:
                    errors.append(f"{target}: HTTP {response.status_code}")
            except Exception as exc:
                errors.append(f"{target}: {exc}")
    return {"ok": sent == len(targets), "sent": sent, "errors": errors}


async def _send_teams(
    message: str,
    conversation_ids: list[str] | None,
    event_type: str,
) -> dict[str, Any]:
    from shogun.db.engine import async_session_factory
    from shogun.db.models.teams import TeamsConfig, TeamsConversation, TeamsNotificationRoute

    async with async_session_factory() as db:
        config = await db.scalar(select(TeamsConfig).limit(1))
        if not config or not config.enabled or not config.proactive_enabled:
            return {"ok": False, "error": "Teams proactive messaging is not enabled", "sent": 0}

        targets = [str(x) for x in (conversation_ids or []) if str(x)]
        if not targets:
            route_result = await db.execute(
                select(TeamsNotificationRoute).where(
                    TeamsNotificationRoute.enabled.is_(True),
                    TeamsNotificationRoute.event_type.in_([event_type, "*"]),
                )
            )
            targets = [r.target_conversation_id for r in route_result.scalars().all()]
        if not targets:
            conversation_result = await db.execute(
                select(TeamsConversation).where(
                    TeamsConversation.installed.is_(True),
                    TeamsConversation.proactive_enabled.is_(True),
                )
            )
            targets = [c.conversation_id for c in conversation_result.scalars().all()]

    targets = list(dict.fromkeys(targets))
    if not targets:
        return {"ok": False, "error": "No Teams conversation target is configured", "sent": 0}
    if not settings.teams_bridge_url or not settings.shogun_internal_api_key:
        return {"ok": False, "error": "Teams bridge URL/internal API key is not configured", "sent": 0}

    sent = 0
    errors: list[str] = []
    url = f"{settings.teams_bridge_url.rstrip('/')}/api/teams/proactive"
    headers = {"Authorization": f"Bearer {settings.shogun_internal_api_key}"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        for conversation_id in targets:
            try:
                response = await client.post(
                    url,
                    headers=headers,
                    json={"conversation_id": conversation_id, "text": message},
                )
                if response.is_success:
                    sent += 1
                else:
                    errors.append(f"{conversation_id}: HTTP {response.status_code}")
            except Exception as exc:
                errors.append(f"{conversation_id}: {exc}")
    return {"ok": sent == len(targets), "sent": sent, "errors": errors}


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
