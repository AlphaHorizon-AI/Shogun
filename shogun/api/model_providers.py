"""Model provider and routing routes."""

from __future__ import annotations

import html
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db, get_model_provider_service, get_model_routing_service
from shogun.api.model_router import router as task_router
from shogun.db.models.model_provider import ModelProvider
from shogun.schemas.common import ApiResponse
from shogun.schemas.models import (
    ModelDiscoveryRequest,
    ModelProviderCreate,
    ModelProviderResponse,
    ModelProviderUpdate,
    ModelReasoningCapabilitiesRequest,
    ModelRoutingProfileCreate,
    ModelRoutingProfileResponse,
    ModelRoutingProfileUpdate,
    ProviderOAuthStartRequest,
)
from shogun.services.model_discovery import ModelDiscoveryError, discover_provider_models
from shogun.services.model_reasoning import reasoning_capability
from shogun.services.model_service import ModelProviderService, ModelRoutingProfileService
from shogun.services.provider_credentials import provider_api_key, reveal_provider_secret
from shogun.services.provider_oauth import (
    ProviderOAuthError,
    complete_provider_oauth,
    disconnect_provider_oauth,
    ensure_provider_access_token,
    start_provider_oauth,
)

router = APIRouter(tags=["Models"])

# ── Providers ────────────────────────────────────────────────

provider_router = APIRouter(prefix="/model-providers")


@provider_router.get("", response_model=ApiResponse)
async def list_providers(svc: ModelProviderService = Depends(get_model_provider_service)):
    records, total = await svc.get_all()
    return ApiResponse(
        data=[ModelProviderResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@provider_router.post("", response_model=ApiResponse, status_code=201)
async def create_provider(
    body: ModelProviderCreate,
    svc: ModelProviderService = Depends(get_model_provider_service),
):
    data = body.model_dump()
    provider_type = body.provider_type.value if hasattr(body.provider_type, "value") else str(body.provider_type)
    auth_type = body.auth_type.value if hasattr(body.auth_type, "value") else str(body.auth_type)
    if auth_type == "oauth" and provider_type not in {"google", "custom"}:
        raise HTTPException(
            status_code=422,
            detail=(
                "OpenAI model API access supports API keys or workload identity tokens, not interactive OAuth."
                if provider_type == "openai"
                else f"{provider_type} is not registered as an OAuth-capable model provider."
            ),
        )
    if auth_type == "oauth" and not reveal_provider_secret((body.config or {}).get("access_token")):
        data["status"] = "not_configured"
    record = await svc.create(**data)
    try:
        from shogun.services.event_logger import EventLogger
        await EventLogger.emit_auth_event(
            "auth.credential_added", f"API provider registered: {body.name}",
            detail={"provider_name": body.name, "provider_type": body.provider_type},
        )
    except Exception:
        pass
    return ApiResponse(data=ModelProviderResponse.model_validate(record))


@provider_router.post("/discover-models", response_model=ApiResponse)
async def discover_models(
    body: ModelDiscoveryRequest,
    svc: ModelProviderService = Depends(get_model_provider_service),
):
    """Return models advertised by a cloud provider using its exact credential."""

    provider_type = body.provider_type.value if hasattr(body.provider_type, "value") else str(body.provider_type)
    base_url = body.base_url or ""
    api_key = reveal_provider_secret(body.api_key) if body.api_key not in {None, "", "********"} else None
    project_id: str | None = None
    if body.provider_id:
        provider = await svc.get_by_id(body.provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        if provider.provider_type != provider_type:
            raise HTTPException(status_code=400, detail="Provider type does not match the saved provider")
        base_url = base_url or provider.base_url or ""
        if provider.auth_type == "oauth":
            api_key = api_key or await ensure_provider_access_token(svc.session, provider)
            await svc.session.commit()
        else:
            api_key = api_key or provider_api_key(provider.config)
        project_id = str((provider.config or {}).get("oauth_project_id") or "") or None
    if provider_type in {"ollama", "lmstudio", "local"}:
        raise HTTPException(status_code=400, detail="Use local model discovery for this provider")
    if not base_url:
        raise HTTPException(status_code=400, detail="Provider base URL is required")
    try:
        models = await discover_provider_models(
            provider_type=provider_type,
            base_url=base_url,
            api_key=api_key,
            project_id=project_id,
        )
    except ModelDiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ApiResponse(data=models, meta={"count": len(models), "provider_type": provider_type})


@provider_router.post("/reasoning-capabilities", response_model=ApiResponse)
async def reasoning_capabilities(body: ModelReasoningCapabilitiesRequest):
    provider_type = body.provider_type.value if hasattr(body.provider_type, "value") else str(body.provider_type)
    return ApiResponse(
        data={model_id: reasoning_capability(provider_type, model_id) for model_id in body.model_ids},
        meta={"provider_type": provider_type},
    )


@provider_router.patch("/{provider_id}", response_model=ApiResponse)
async def update_provider(
    provider_id: uuid.UUID,
    body: ModelProviderUpdate,
    svc: ModelProviderService = Depends(get_model_provider_service),
):
    current = await svc.get_by_id(provider_id)
    if not current:
        raise HTTPException(status_code=404, detail="Provider not found")
    requested_auth = body.auth_type.value if hasattr(body.auth_type, "value") else body.auth_type
    effective_auth = requested_auth or current.auth_type
    if effective_auth == "oauth" and current.provider_type not in {"google", "custom"}:
        raise HTTPException(
            status_code=422,
            detail=(
                "OpenAI model API access supports API keys or workload identity tokens, not interactive OAuth."
                if current.provider_type == "openai"
                else f"{current.provider_type} is not registered as an OAuth-capable model provider."
            ),
        )
    record = await svc.update(provider_id, **body.model_dump(exclude_unset=True))
    if not record:
        raise HTTPException(status_code=404, detail="Provider not found")
    if record.auth_type == "oauth" and not reveal_provider_secret((record.config or {}).get("access_token")):
        record.status = "not_configured"
        await svc.session.flush()
    try:
        from shogun.services.event_logger import EventLogger
        await EventLogger.emit_auth_event(
            "auth.credential_updated", f"API provider updated: {record.name}",
            detail={"provider_id": str(provider_id), "provider_name": record.name},
        )
    except Exception:
        pass
    return ApiResponse(data=ModelProviderResponse.model_validate(record))


@provider_router.post("/{provider_id}/oauth/start", response_model=ApiResponse)
async def start_oauth(
    provider_id: uuid.UUID,
    body: ProviderOAuthStartRequest,
    db: AsyncSession = Depends(get_db),
):
    provider = await db.get(ModelProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    try:
        result = start_provider_oauth(provider, body.return_origin)
    except ProviderOAuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse(data=result)


@provider_router.get("/oauth/callback", response_class=HTMLResponse)
async def oauth_callback(
    state: str = Query(..., min_length=16, max_length=500),
    code: str | None = Query(None, max_length=10_000),
    error: str | None = Query(None, max_length=500),
    db: AsyncSession = Depends(get_db),
):
    status = "error"
    message = error or "OAuth provider did not return an authorization code"
    provider_id = ""
    return_origin = ""
    if code and not error:
        try:
            provider, return_origin = await complete_provider_oauth(db, state=state, code=code)
            await db.commit()
            status = "success"
            message = "OAuth connection completed"
            provider_id = str(provider.id)
        except ProviderOAuthError as exc:
            await db.rollback()
            message = str(exc)
    payload = json.dumps(
        {"type": "shogun.provider-oauth", "status": status, "message": message, "providerId": provider_id}
    ).replace("</", "<\\/")
    target = json.dumps(return_origin or "*")
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'><title>Shogun OAuth</title>"
        "<body style='font-family:system-ui;background:#080b14;color:#e5e7eb;padding:2rem'>"
        f"<h2>{'Connection complete' if status == 'success' else 'Connection failed'}</h2>"
        f"<p>{html.escape(message)}</p><script>"
        f"if(window.opener){{window.opener.postMessage({payload},{target});setTimeout(()=>window.close(),500);}}"
        "</script></body>"
    )


@provider_router.post("/{provider_id}/oauth/disconnect", response_model=ApiResponse)
async def disconnect_oauth(provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    provider = await db.get(ModelProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    disconnect_provider_oauth(provider)
    await db.commit()
    return ApiResponse(data={"status": "not_configured", "provider_id": str(provider_id)})


@provider_router.post("/{provider_id}/test", response_model=ApiResponse)
async def test_provider(provider_id: uuid.UUID):
    return ApiResponse(data={"status": "test_not_implemented", "provider_id": str(provider_id)})


@provider_router.delete("/{provider_id}", response_model=ApiResponse)
async def delete_provider(
    provider_id: uuid.UUID,
    svc: ModelProviderService = Depends(get_model_provider_service),
):
    deleted = await svc.delete(provider_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Provider not found")
    try:
        from shogun.services.event_logger import EventLogger
        await EventLogger.emit_auth_event(
            "auth.credential_removed", "API provider removed",
            detail={"provider_id": str(provider_id)},
        )
    except Exception:
        pass
    return ApiResponse(data={"deleted": True})


# ── Routing Profiles ─────────────────────────────────────────

routing_router = APIRouter(prefix="/model-routing-profiles")


@routing_router.get("", response_model=ApiResponse)
async def list_routing_profiles(svc: ModelRoutingProfileService = Depends(get_model_routing_service)):
    records, total = await svc.get_all()
    return ApiResponse(
        data=[ModelRoutingProfileResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@routing_router.post("", response_model=ApiResponse, status_code=201)
async def create_routing_profile(
    body: ModelRoutingProfileCreate,
    svc: ModelRoutingProfileService = Depends(get_model_routing_service),
):
    data = body.model_dump()
    data["rules"] = [r.model_dump() if hasattr(r, "model_dump") else r for r in data.get("rules", [])]
    try:
        record = await svc.create(**data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(data=ModelRoutingProfileResponse.model_validate(record))


@routing_router.patch("/{profile_id}", response_model=ApiResponse)
async def update_routing_profile(
    profile_id: uuid.UUID,
    body: ModelRoutingProfileUpdate,
    svc: ModelRoutingProfileService = Depends(get_model_routing_service),
):
    update_data = body.model_dump(exclude_unset=True)
    if "rules" in update_data and update_data["rules"] is not None:
        update_data["rules"] = [r.model_dump() if hasattr(r, "model_dump") else r for r in update_data["rules"]]
    try:
        record = await svc.update(profile_id, **update_data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not record:
        raise HTTPException(status_code=404, detail="Routing profile not found")
    return ApiResponse(data=ModelRoutingProfileResponse.model_validate(record))


@routing_router.delete("/{profile_id}", response_model=ApiResponse)
async def delete_routing_profile(
    profile_id: uuid.UUID,
    svc: ModelRoutingProfileService = Depends(get_model_routing_service),
):
    try:
        deleted = await svc.delete(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Routing profile not found")
    return ApiResponse(data={"deleted": True})


router.include_router(provider_router)
router.include_router(routing_router)
router.include_router(task_router)
