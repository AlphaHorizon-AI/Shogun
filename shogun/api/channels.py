"""Channel routes — Telegram integration."""

from __future__ import annotations

from fastapi import APIRouter

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
    return ApiResponse(data=result)


@router.post("/telegram/test", response_model=ApiResponse)
async def test_telegram(body: dict):
    chat_id = body.get("chat_id", "")
    if not chat_id:
        return ApiResponse(data={"ok": False, "error": "chat_id is required."})
    result = await channel_svc.test_message(chat_id)
    return ApiResponse(data=result)


@router.delete("/telegram/disconnect", response_model=ApiResponse)
async def disconnect_telegram():
    result = await channel_svc.disconnect_telegram()
    return ApiResponse(data=result)
