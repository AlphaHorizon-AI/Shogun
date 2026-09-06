"""Manual recovery and callback endpoints for direct ChatGPT OAuth."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.db.models.model_provider import ModelProvider
from shogun.schemas.common import ApiResponse
from shogun.services.oauth_coordination import serialized_provider_auth
from shogun.services.openai_oauth import complete_sign_in, is_openai_oauth, retire_attempts
from shogun.services.provider_oauth import ProviderOAuthError

router = APIRouter()


class CompleteRequest(BaseModel):
    flow_id: str = Field(min_length=16, max_length=500)
    callback_url: str = Field(min_length=1, max_length=16384)


@router.post("/{provider_id}/oauth/complete", response_model=ApiResponse)
async def complete_manual(provider_id: uuid.UUID, body: CompleteRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await complete_sign_in(db, provider_id, state=body.flow_id, callback_url=body.callback_url)
        return ApiResponse(data=result)
    except ProviderOAuthError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{provider_id}/oauth/cancel", response_model=ApiResponse)
@serialized_provider_auth
async def cancel_sign_in(provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    provider = await db.get(ModelProvider, provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    if not is_openai_oauth(provider):
        raise HTTPException(422, "This provider does not use direct ChatGPT OAuth.")
    retire_attempts(provider_id)
    return ApiResponse(data={"status": "cancelled"})


@router.get("/oauth/callback/chatgpt/{provider_id}", response_class=HTMLResponse)
async def callback(
    provider_id: uuid.UUID,
    request: Request,
    state: str = Query(min_length=16, max_length=500),
    code: str = Query("", max_length=10000),
    error: str | None = Query(None, max_length=500),
    db: AsyncSession = Depends(get_db),
):
    fields = request.query_params.multi_items()
    if len(fields) > 12 or len({key for key, _ in fields}) != len(fields):
        raise HTTPException(422, "Invalid OAuth callback parameters.")
    result = "success"
    try:
        await complete_sign_in(db, provider_id, state=state, code=code, error=error)
    except ProviderOAuthError:
        result = "error"
    except Exception:
        result = "error"
    return RedirectResponse(
        f"/api/v1/model-providers/oauth/callback/chatgpt/result/{result}",
        status_code=303,
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )


@router.get("/oauth/callback/chatgpt/result/{result}", response_class=HTMLResponse)
async def callback_result(result: Literal["success", "error"]):
    message = (
        "ChatGPT connected. Return to Shogun."
        if result == "success"
        else "Sign-in could not complete. Return to Shogun and start again."
    )
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'><title>Shogun ChatGPT sign-in</title>"
        f"<main><h1>ChatGPT sign-in</h1><p>{message}</p></main>",
        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"},
    )
