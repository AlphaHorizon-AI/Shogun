"""Model provider and routing routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_model_provider_service, get_model_routing_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.models import (
    ModelDiscoveryRequest,
    ModelProviderCreate,
    ModelProviderResponse,
    ModelProviderUpdate,
    ModelRoutingProfileCreate,
    ModelRoutingProfileResponse,
    ModelRoutingProfileUpdate,
)
from shogun.services.model_discovery import ModelDiscoveryError, discover_provider_models
from shogun.services.model_service import ModelProviderService, ModelRoutingProfileService
from shogun.services.provider_credentials import provider_api_key, reveal_provider_secret

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
    record = await svc.create(**body.model_dump())
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
    if body.provider_id:
        provider = await svc.get_by_id(body.provider_id)
        if not provider:
            raise HTTPException(status_code=404, detail="Provider not found")
        if provider.provider_type != provider_type:
            raise HTTPException(status_code=400, detail="Provider type does not match the saved provider")
        base_url = base_url or provider.base_url or ""
        api_key = api_key or provider_api_key(provider.config)
    if provider_type in {"ollama", "lmstudio", "local"}:
        raise HTTPException(status_code=400, detail="Use local model discovery for this provider")
    if not base_url:
        raise HTTPException(status_code=400, detail="Provider base URL is required")
    try:
        models = await discover_provider_models(
            provider_type=provider_type,
            base_url=base_url,
            api_key=api_key,
        )
    except ModelDiscoveryError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return ApiResponse(data=models, meta={"count": len(models), "provider_type": provider_type})


@provider_router.patch("/{provider_id}", response_model=ApiResponse)
async def update_provider(
    provider_id: uuid.UUID,
    body: ModelProviderUpdate,
    svc: ModelProviderService = Depends(get_model_provider_service),
):
    record = await svc.update(provider_id, **body.model_dump(exclude_unset=True))
    if not record:
        raise HTTPException(status_code=404, detail="Provider not found")
    try:
        from shogun.services.event_logger import EventLogger
        await EventLogger.emit_auth_event(
            "auth.credential_updated", f"API provider updated: {record.name}",
            detail={"provider_id": str(provider_id), "provider_name": record.name},
        )
    except Exception:
        pass
    return ApiResponse(data=ModelProviderResponse.model_validate(record))


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
            "auth.credential_removed", f"API provider removed",
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
    record = await svc.create(**data)
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
    record = await svc.update(profile_id, **update_data)
    if not record:
        raise HTTPException(status_code=404, detail="Routing profile not found")
    return ApiResponse(data=ModelRoutingProfileResponse.model_validate(record))


@routing_router.delete("/{profile_id}", response_model=ApiResponse)
async def delete_routing_profile(
    profile_id: uuid.UUID,
    svc: ModelRoutingProfileService = Depends(get_model_routing_service),
):
    deleted = await svc.delete(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Routing profile not found")
    return ApiResponse(data={"deleted": True})


router.include_router(provider_router)
router.include_router(routing_router)

from shogun.api.model_router import router as task_router
router.include_router(task_router)
