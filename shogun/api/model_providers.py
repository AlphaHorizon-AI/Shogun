"""Model provider and routing routes."""

from __future__ import annotations

import asyncio
import html
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.chatgpt_oauth import router as chatgpt_oauth_router
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
from shogun.services import openai_oauth
from shogun.services.codex_app_server import CodexAppServerError, get_codex_app_server
from shogun.services.model_discovery import ModelDiscoveryError, discover_provider_models
from shogun.services.model_reasoning import reasoning_capability
from shogun.services.model_service import ModelProviderService, ModelRoutingProfileService
from shogun.services.oauth_coordination import serialized_provider_auth
from shogun.services.provider_browser import (
    ProviderBrowserError,
    open_default_browser,
    provider_setup_url,
)
from shogun.services.provider_credentials import provider_api_key, reveal_provider_secret
from shogun.services.provider_oauth import (
    ProviderOAuthError,
    accept_provider_oauth,
    complete_provider_oauth,
    disconnect_provider_oauth,
    ensure_provider_access_token,
    provider_oauth_status,
    reject_provider_oauth,
    start_provider_oauth,
)

router = APIRouter(tags=["Models"])

_codex_login_providers: dict[str, uuid.UUID] = {}

# ── Providers ────────────────────────────────────────────────

provider_router = APIRouter(prefix="/model-providers")
provider_router.include_router(chatgpt_oauth_router)


def _is_loopback_request(request: Request) -> bool:
    return bool(request.client and request.client.host.casefold() in {"127.0.0.1", "::1", "localhost"})


async def _open_for_local_desktop(request: Request, url: str) -> bool:
    if not _is_loopback_request(request):
        return False
    return await asyncio.to_thread(open_default_browser, url)


async def _sync_codex_provider(db: AsyncSession, provider: ModelProvider) -> list[str]:
    client = get_codex_app_server()
    state = await client.account(refresh=False)
    account = state.get("account") or {}
    if account.get("type") != "chatgpt":
        raise CodexAppServerError("ChatGPT/Codex sign-in has not completed.", status_code=401)
    catalog = await client.list_models()
    models = sorted(
        {
            str(item.get("model") or item.get("id") or "").strip()
            for item in catalog
            if str(item.get("model") or item.get("id") or "").strip()
        },
        key=str.casefold,
    )
    config = dict(provider.config or {})
    config.update(
        {
            "codex_account_connected": True,
            "codex_plan_type": account.get("planType"),
            "models": models,
        }
    )
    provider.config = config
    provider.status = "connected"
    provider.health_status = "healthy"
    provider.base_url = None
    await db.flush()
    return models


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
    if auth_type == "chatgpt" and provider_type != "openai":
        raise HTTPException(status_code=422, detail="ChatGPT/Codex subscription sign-in is available only for OpenAI.")
    if auth_type == "oauth" and provider_type not in {"openai", "google", "custom"}:
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
    if auth_type == "oauth" and provider_type == "openai":
        data["base_url"] = openai_oauth.RESPONSES_URL
        data["status"] = "not_configured"
        excluded = openai_oauth.GRANT_KEYS | {"api_key", "api-key", "token", "oauth_client_secret"}
        data["config"] = {key: value for key, value in (body.config or {}).items() if key not in excluded}
    if auth_type == "chatgpt":
        data["status"] = "not_configured"
        data["base_url"] = None
        config = dict(data.get("config") or {})
        for key in ("api_key", "api-key", "token", "access_token", "refresh_token", "oauth_client_secret"):
            config.pop(key, None)
        config["codex_account_connected"] = False
        data["config"] = config
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
        if openai_oauth.is_openai_oauth(provider):
            raise HTTPException(
                422, "Add exact ChatGPT subscription model IDs in Active Models. "
                "Platform model discovery is unavailable for this connection.",
            )
        if provider.auth_type == "chatgpt":
            try:
                state = await get_codex_app_server().account(refresh=False)
                if (state.get("account") or {}).get("type") != "chatgpt":
                    raise ModelDiscoveryError("Sign in with ChatGPT/Codex before discovering subscription models.")
                catalog = await get_codex_app_server().list_models()
                models = sorted(
                    {
                        str(item.get("model") or item.get("id") or "").strip()
                        for item in catalog
                        if str(item.get("model") or item.get("id") or "").strip()
                    },
                    key=str.casefold,
                )
            except CodexAppServerError as exc:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
            return ApiResponse(data=models, meta={"count": len(models), "provider_type": provider_type})
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
@serialized_provider_auth
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
    if effective_auth == "chatgpt" and current.provider_type != "openai":
        raise HTTPException(status_code=422, detail="ChatGPT/Codex subscription sign-in is available only for OpenAI.")
    if effective_auth == "oauth" and current.provider_type not in {"openai", "google", "custom"}:
        raise HTTPException(
            status_code=422,
            detail=(
                "OpenAI model API access supports API keys or workload identity tokens, not interactive OAuth."
                if current.provider_type == "openai"
                else f"{current.provider_type} is not registered as an OAuth-capable model provider."
            ),
        )
    update_data = body.model_dump(exclude_unset=True)
    if effective_auth != current.auth_type:
        openai_oauth.retire_attempts(provider_id)
        if openai_oauth.is_openai_oauth(current) and body.base_url in {None, "", openai_oauth.RESPONSES_URL}:
            update_data["base_url"] = "https://api.openai.com/v1"
    if effective_auth == "oauth" and current.provider_type == "openai":
        update_data["base_url"] = openai_oauth.RESPONSES_URL
        incoming = dict(update_data.get("config") or current.config or {})
        for key in openai_oauth.GRANT_KEYS | {"api_key", "api-key", "token", "oauth_client_secret"}:
            incoming.pop(key, None)
        if openai_oauth.is_openai_oauth(current):
            incoming.update({
                key: value for key, value in (current.config or {}).items() if key in openai_oauth.GRANT_KEYS
            })
        update_data["config"] = incoming
    if current.auth_type == "chatgpt" and effective_auth != "chatgpt":
        try:
            await get_codex_app_server().logout()
        except CodexAppServerError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=f"Disconnect ChatGPT/Codex before changing the authentication method: {exc}",
            ) from exc
    if effective_auth == "chatgpt":
        update_data["base_url"] = None
        if "config" in update_data:
            config = dict(update_data.get("config") or {})
            for key in ("api_key", "api-key", "token", "access_token", "refresh_token", "oauth_client_secret"):
                config.pop(key, None)
            update_data["config"] = config
    record = await svc.update(provider_id, **update_data)
    if not record:
        raise HTTPException(status_code=404, detail="Provider not found")
    if record.auth_type == "oauth" and not reveal_provider_secret((record.config or {}).get("access_token")):
        record.status = "not_configured"
        await svc.session.flush()
    if record.auth_type == "chatgpt":
        try:
            await _sync_codex_provider(svc.session, record)
        except CodexAppServerError:
            config = dict(record.config or {})
            config["codex_account_connected"] = False
            record.config = config
            record.status = "not_configured"
            record.health_status = "unknown"
            record.base_url = None
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
@serialized_provider_auth
async def start_oauth(
    provider_id: uuid.UUID,
    body: ProviderOAuthStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    provider = await db.get(ModelProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    try:
        if openai_oauth.is_openai_oauth(provider):
            if not _is_loopback_request(request):
                raise ProviderOAuthError("Open Shogun on this computer's localhost address to connect ChatGPT.")
            result = openai_oauth.start_sign_in(provider, body.return_origin)
        else:
            result = start_provider_oauth(provider, body.return_origin)
    except ProviderOAuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        result["browser_opened"] = await _open_for_local_desktop(request, result["authorization_url"])
    except ProviderBrowserError:
        result["browser_opened"] = False
    return ApiResponse(data=result)


@provider_router.post("/{provider_id}/codex/start", response_model=ApiResponse)
async def start_codex_login(
    provider_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    provider = await db.get(ModelProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if provider.provider_type != "openai" or provider.auth_type != "chatgpt":
        raise HTTPException(status_code=422, detail="This provider does not use ChatGPT/Codex subscription sign-in.")
    client = get_codex_app_server()
    try:
        state = await client.account(refresh=False)
        if (state.get("account") or {}).get("type") == "chatgpt":
            models = await _sync_codex_provider(db, provider)
            await db.commit()
            return ApiResponse(
                data={"status": "success", "already_connected": True, "models": models}
            )
        result = await client.start_chatgpt_login()
    except CodexAppServerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    login_id = str(result.get("loginId") or "")
    authorization_url = str(result.get("authUrl") or "")
    if not login_id or not authorization_url:
        raise HTTPException(status_code=502, detail="Codex did not return a ChatGPT authorization URL.")
    _codex_login_providers[login_id] = provider_id
    try:
        browser_opened = await _open_for_local_desktop(request, authorization_url)
    except ProviderBrowserError:
        browser_opened = False
    return ApiResponse(
        data={
            "status": "pending",
            "flow_id": login_id,
            "authorization_url": authorization_url,
            "browser_opened": browser_opened,
        }
    )


@provider_router.get("/{provider_id}/codex/status", response_model=ApiResponse)
async def codex_login_status(
    provider_id: uuid.UUID,
    flow_id: str = Query(..., min_length=16, max_length=500),
    db: AsyncSession = Depends(get_db),
):
    provider = await db.get(ModelProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if _codex_login_providers.get(flow_id) != provider_id:
        raise HTTPException(status_code=404, detail="ChatGPT/Codex login flow not found")
    client = get_codex_app_server()
    result = client.login_result(flow_id)
    if result and not result.get("success"):
        _codex_login_providers.pop(flow_id, None)
        return ApiResponse(data={"status": "error", "message": result.get("error") or "Sign-in failed."})
    try:
        state = await client.account(refresh=False)
        if (state.get("account") or {}).get("type") != "chatgpt":
            return ApiResponse(data={"status": "pending"})
        models = await _sync_codex_provider(db, provider)
        await db.commit()
    except CodexAppServerError as exc:
        if result and result.get("success"):
            _codex_login_providers.pop(flow_id, None)
            return ApiResponse(data={"status": "error", "message": str(exc)})
        return ApiResponse(data={"status": "pending"})
    _codex_login_providers.pop(flow_id, None)
    return ApiResponse(
        data={
            "status": "success",
            "message": "ChatGPT/Codex subscription connected.",
            "models": models,
        }
    )


@provider_router.post("/{provider_id}/codex/disconnect", response_model=ApiResponse)
async def disconnect_codex(provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    provider = await db.get(ModelProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if provider.auth_type != "chatgpt":
        raise HTTPException(status_code=422, detail="This provider does not use ChatGPT/Codex sign-in.")
    try:
        await get_codex_app_server().logout()
    except CodexAppServerError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    config = dict(provider.config or {})
    config["codex_account_connected"] = False
    config.pop("codex_plan_type", None)
    provider.config = config
    provider.status = "not_configured"
    provider.health_status = "unknown"
    await db.commit()
    return ApiResponse(data={"status": "not_configured", "provider_id": str(provider_id)})


@provider_router.get("/{provider_id}/oauth/status", response_model=ApiResponse)
async def oauth_status(
    provider_id: uuid.UUID,
    flow_id: str = Query(..., min_length=16, max_length=500),
    db: AsyncSession = Depends(get_db),
):
    provider = await db.get(ModelProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    if openai_oauth.is_openai_oauth(provider):
        return ApiResponse(data=openai_oauth.sign_in_status(provider_id, flow_id))
    return ApiResponse(data=provider_oauth_status(provider_id, flow_id))


@provider_router.post("/credential-setup/{provider_type}/open", response_model=ApiResponse)
async def open_credential_setup(
    provider_type: str,
    request: Request,
    auth_type: str = Query("api_key", min_length=1, max_length=30),
):
    try:
        url = provider_setup_url(provider_type, auth_type)
        browser_opened = await _open_for_local_desktop(request, url)
    except ProviderBrowserError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ApiResponse(data={"url": url, "browser_opened": browser_opened})


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
    if error or not code:
        try:
            pending_provider_id, return_origin = reject_provider_oauth(state, message)
            provider_id = str(pending_provider_id)
        except ProviderOAuthError as exc:
            message = str(exc)
    else:
        try:
            provider, return_origin = await complete_provider_oauth(db, state=state, code=code)
            await db.commit()
            accept_provider_oauth(state)
            status = "success"
            message = "OAuth connection completed"
            provider_id = str(provider.id)
        except ProviderOAuthError as exc:
            await db.rollback()
            message = str(exc)
        except Exception:
            await db.rollback()
            try:
                reject_provider_oauth(state, "OAuth tokens could not be saved")
            except ProviderOAuthError:
                pass
            message = "OAuth tokens could not be saved"
    payload = json.dumps(
        {"type": "shogun.provider-oauth", "status": status, "message": message, "providerId": provider_id}
    ).replace("</", "<\\/")
    target = json.dumps(return_origin or "*")
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'><title>Shogun OAuth</title>"
        "<body style='font-family:system-ui;background:#080b14;color:#e5e7eb;padding:2rem'>"
        f"<h2>{'Connection complete' if status == 'success' else 'Connection failed'}</h2>"
        f"<p>{html.escape(message)}</p><p>You can close this tab and return to Shogun.</p><script>"
        f"if(window.opener){{window.opener.postMessage({payload},{target});setTimeout(()=>window.close(),500);}}"
        "</script></body>"
    )


@provider_router.post("/{provider_id}/oauth/disconnect", response_model=ApiResponse)
@serialized_provider_auth
async def disconnect_oauth(provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    provider = await db.get(ModelProvider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    disconnect_provider_oauth(provider)
    openai_oauth.retire_attempts(provider_id)
    provider.config = {key: value for key, value in provider.config.items() if key not in openai_oauth.GRANT_KEYS}
    await db.commit()
    return ApiResponse(data={"status": "not_configured", "provider_id": str(provider_id)})


@provider_router.post("/{provider_id}/test", response_model=ApiResponse)
async def test_provider(provider_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    provider = await db.get(ModelProvider, provider_id)
    if not provider:
        raise HTTPException(404, "Provider not found")
    if openai_oauth.is_openai_oauth(provider):
        return ApiResponse(data=await openai_oauth.verify_connection(db, provider))
    return ApiResponse(data={"status": "test_not_implemented", "provider_id": str(provider_id)})


@provider_router.delete("/{provider_id}", response_model=ApiResponse)
@serialized_provider_auth
async def delete_provider(
    provider_id: uuid.UUID,
    svc: ModelProviderService = Depends(get_model_provider_service),
):
    current = await svc.get_by_id(provider_id)
    if not current:
        raise HTTPException(status_code=404, detail="Provider not found")
    if current.auth_type == "chatgpt":
        try:
            await get_codex_app_server().logout()
        except CodexAppServerError as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=f"ChatGPT/Codex could not be disconnected before deletion: {exc}",
            ) from exc
    deleted = await svc.delete(provider_id)
    openai_oauth.retire_attempts(provider_id)
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
