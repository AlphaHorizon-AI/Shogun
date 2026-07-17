"""Channel routes — Telegram integration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from shogun.schemas.channels import TelegramConnectRequest, TelegramStatusResponse
from shogun.schemas.common import ApiResponse
from shogun.services.channel_service import ChannelService

router = APIRouter(prefix="/channels", tags=["Channels"])
channel_svc = ChannelService()


@router.get("/telegram/status", response_model=ApiResponse)
async def telegram_status():
    status = await channel_svc.get_telegram_status()
    return ApiResponse(data=status)


@router.post("/telegram/connect", response_model=ApiResponse)
async def connect_telegram(body: TelegramConnectRequest):
    result = await channel_svc.connect_telegram(
        bot_token=body.bot_token,
        mode=body.mode,
        allowed_chat_ids=body.allowed_chat_ids or [],
        webhook_url=body.webhook_url,
    )
    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_auth_event(
            "auth.channel_connected",
            "Telegram bot connected",
            detail={"channel": "telegram", "mode": body.mode},
        )
    except Exception:
        pass
    return ApiResponse(data=result)


@router.post("/telegram/test", response_model=ApiResponse)
async def test_telegram(body: dict):
    chat_id = body.get("chat_id", "")
    if not chat_id:
        return ApiResponse(data={"ok": False, "error": "chat_id is required."})
    result = await channel_svc.test_message(chat_id)
    return ApiResponse(data=result)


@router.post("/telegram/detect", response_model=ApiResponse)
async def detect_chat_id():
    result = await channel_svc.detect_chat_id()
    return ApiResponse(data=result)


@router.get("/telegram/topics", response_model=ApiResponse)
async def list_telegram_topics():
    """List every observed forum thread and its durable local topic name."""
    from shogun.services.telegram_poller import list_telegram_topic_mappings

    return ApiResponse(data=list_telegram_topic_mappings())


@router.put("/telegram/topics/{chat_id}/{thread_id}", response_model=ApiResponse)
async def update_telegram_topic(chat_id: str, thread_id: int, body: dict):
    """Set the name for a pre-existing Telegram forum topic."""
    from shogun.services.telegram_poller import set_telegram_topic_mapping

    try:
        topic = set_telegram_topic_mapping(chat_id, thread_id, str(body.get("name") or ""))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse(data=topic)


@router.delete("/telegram/disconnect", response_model=ApiResponse)
async def disconnect_telegram():
    result = await channel_svc.disconnect_telegram()
    try:
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit_auth_event(
            "auth.channel_disconnected",
            "Telegram bot disconnected",
            detail={"channel": "telegram"},
        )
    except Exception:
        pass
    return ApiResponse(data=result)
