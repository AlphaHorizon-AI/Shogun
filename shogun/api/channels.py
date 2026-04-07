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
    result = await channel_svc.connect_telegram(body.bot_token, body.mode)
    return ApiResponse(data=result)


@router.post("/telegram/test", response_model=ApiResponse)
async def test_telegram():
    return ApiResponse(data={"message": "Test message not yet implemented"})
