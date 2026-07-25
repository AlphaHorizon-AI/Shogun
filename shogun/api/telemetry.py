"""Authenticated local administration API for installation telemetry."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from shogun.api.infrastructure_auth import require_infrastructure_admin
from shogun.telemetry.config import CONSENT_NOTICE_VERSION
from shogun.telemetry.models import EventType
from shogun.telemetry.service import telemetry_service

router = APIRouter(prefix="/telemetry", tags=["privacy-telemetry"])


class EnableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notice_version: str
    confirmed: bool


@router.get("/status")
async def get_status(_actor: str = Depends(require_infrastructure_admin)):
    return telemetry_service.status()


@router.get("/preview")
async def preview(_actor: str = Depends(require_infrastructure_admin)):
    return telemetry_service.preview(EventType.ACTIVE_HEARTBEAT)


@router.get("/identifier")
async def show_identifier(_actor: str = Depends(require_infrastructure_admin)):
    return {"installation_id": telemetry_service.identifier()}


@router.post("/enable")
async def enable(body: EnableRequest, actor: str = Depends(require_infrastructure_admin)):
    if not body.confirmed:
        raise HTTPException(400, "Explicit confirmation is required")
    if body.notice_version != CONSENT_NOTICE_VERSION:
        raise HTTPException(400, f"Notice version {CONSENT_NOTICE_VERSION} must be accepted")
    try:
        return await telemetry_service.enable(body.notice_version, actor=actor)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/disable")
async def disable(_actor: str = Depends(require_infrastructure_admin)):
    return await telemetry_service.disable(delete_remote=True)


@router.post("/dismiss")
async def dismiss(_actor: str = Depends(require_infrastructure_admin)):
    return telemetry_service.dismiss_prompt()


@router.post("/delete")
async def delete(_actor: str = Depends(require_infrastructure_admin)):
    return await telemetry_service.delete_remote()


@router.post("/test")
async def send_test(_actor: str = Depends(require_infrastructure_admin)):
    try:
        return await telemetry_service.send_test()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
