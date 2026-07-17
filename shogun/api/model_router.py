"""Model registry, task-aware routing, decisions, and usage APIs."""

from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.db.models.model_router import ModelRegistryEntry
from shogun.schemas.common import ApiResponse
from shogun.schemas.model_router import (
    TASK_TYPES,
    ActiveProfileRequest,
    ModelRegistryCreate,
    ModelRegistryResponse,
    ModelRegistryUpdate,
    ModelRouteRequest,
    ModelUsageCreate,
)
from shogun.schemas.models import ModelRoutingProfileResponse, ModelRoutingProfileUpdate
from shogun.services.model_router import (
    ModelRegistryService,
    ModelRoutingService,
    ModelUsageLogger,
    NoEligibleModelError,
    read_routing_config,
)
from shogun.services.model_service import ModelRoutingProfileService

router = APIRouter(prefix="/models", tags=["Model Router"])


def _registry_response(item: ModelRegistryEntry) -> ModelRegistryResponse:
    return ModelRegistryResponse.model_validate(item)


@router.get("/routing/profiles", response_model=ApiResponse)
async def profiles(db: AsyncSession = Depends(get_db)):
    service = ModelRoutingService(db)
    records = await service.ensure_defaults()
    await db.commit()
    return ApiResponse(
        data=[ModelRoutingProfileResponse.model_validate(item) for item in records],
        meta={"active": (await service.active_profile()).name, "config": read_routing_config()},
    )


@router.get("/routing/profiles/active", response_model=ApiResponse)
async def active_profile(db: AsyncSession = Depends(get_db)):
    profile = await ModelRoutingService(db).active_profile()
    return ApiResponse(data=ModelRoutingProfileResponse.model_validate(profile), meta={"config": read_routing_config()})


@router.post("/routing/profiles/active", response_model=ApiResponse)
async def set_active_profile(body: ActiveProfileRequest, db: AsyncSession = Depends(get_db)):
    service = ModelRoutingService(db)
    profiles = await service.ensure_defaults()
    wanted = str(body.profile_id) if body.profile_id else (body.profile or "").lower().replace(" ", "_")
    profile = next(
        (item for item in profiles if str(item.id) == wanted or item.name.lower().replace(" ", "_") == wanted), None
    )
    if not profile:
        raise HTTPException(404, "Routing profile not found.")
    await service.set_active(profile)
    await db.commit()
    return ApiResponse(data=ModelRoutingProfileResponse.model_validate(profile))


@router.post("/routing/profiles/{profile_id}/update", response_model=ApiResponse)
async def update_profile(profile_id: uuid.UUID, body: ModelRoutingProfileUpdate, db: AsyncSession = Depends(get_db)):
    service = ModelRoutingProfileService(db)
    data = body.model_dump(exclude_unset=True)
    if "rules" in data and data["rules"] is not None:
        data["rules"] = [item.model_dump() if hasattr(item, "model_dump") else item for item in data["rules"]]
    record = await service.update(profile_id, **data)
    if not record:
        raise HTTPException(404, "Routing profile not found.")
    await db.commit()
    return ApiResponse(data=ModelRoutingProfileResponse.model_validate(record))


@router.get("/registry", response_model=ApiResponse)
async def registry(db: AsyncSession = Depends(get_db)):
    records = await ModelRegistryService(db).list()
    await db.commit()
    return ApiResponse(data=[_registry_response(item) for item in records], meta={"total": len(records)})


@router.post("/registry", response_model=ApiResponse, status_code=201)
async def create_registry(body: ModelRegistryCreate, db: AsyncSession = Depends(get_db)):
    item = await ModelRegistryService(db).create(body.model_dump())
    await db.commit()
    await ModelRoutingService._audit(
        "model.registry.model_added",
        f"Model added to registry: {item.model_id}",
        model_used=item.model_id,
        provider_used=item.provider,
    )
    return ApiResponse(data=_registry_response(item))


@router.patch("/registry/{model_id}", response_model=ApiResponse)
async def update_registry(model_id: uuid.UUID, body: ModelRegistryUpdate, db: AsyncSession = Depends(get_db)):
    item = await ModelRegistryService(db).update(model_id, body.model_dump(exclude_unset=True))
    if not item:
        raise HTTPException(404, "Registry model not found.")
    await db.commit()
    event = "model.registry.model_disabled" if body.enabled is False else "model.registry.model_updated"
    await ModelRoutingService._audit(
        event, f"Registry model updated: {item.model_id}", model_used=item.model_id, provider_used=item.provider
    )
    return ApiResponse(data=_registry_response(item))


@router.delete("/registry/{model_id}", response_model=ApiResponse)
async def delete_registry(model_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    if not await ModelRegistryService(db).delete(model_id):
        raise HTTPException(404, "Registry model not found.")
    await db.commit()
    return ApiResponse(data={"deleted": True})


@router.post("/registry/{model_id}/test", response_model=ApiResponse)
async def test_registry(model_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(ModelRegistryEntry, model_id)
    if not item or not item.provider_id:
        raise HTTPException(404, "Connected registry model not found.")
    from shogun.db.models.model_provider import ModelProvider

    provider = await db.get(ModelProvider, item.provider_id)
    if not provider or provider.status != "connected":
        raise HTTPException(409, "Model provider is not connected.")
    base = (provider.base_url or "").rstrip("/")
    headers = {"Authorization": f"Bearer {provider.config.get('api_key')}"} if provider.config.get("api_key") else {}
    url = f"{base}/api/tags" if provider.provider_type == "ollama" else f"{base}/models"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers)
        response.raise_for_status()
    except Exception as exc:
        raise HTTPException(502, f"Model connection test failed: {exc}") from exc
    return ApiResponse(data={"status": "connected", "model_id": item.model_id, "provider": item.provider})


@router.post("/route", response_model=ApiResponse)
async def route(body: ModelRouteRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await ModelRoutingService(db).route(body, persist=True)
    except NoEligibleModelError as exc:
        raise HTTPException(409, str(exc)) from exc
    await db.commit()
    return ApiResponse(data=result.payload)


@router.post("/route/preview", response_model=ApiResponse)
async def preview_route(body: ModelRouteRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await ModelRoutingService(db).route(body, persist=False)
    except NoEligibleModelError as exc:
        raise HTTPException(409, str(exc)) from exc
    return ApiResponse(data=result.payload)


@router.get("/routing/decisions", response_model=ApiResponse)
async def decisions(
    run_id: uuid.UUID | None = None,
    stack_run_id: uuid.UUID | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    records = await ModelRoutingService(db).decisions(run_id, stack_run_id, limit)
    return ApiResponse(data=records, meta={"total": len(records)})


@router.get("/routing/decisions/{run_id}", response_model=ApiResponse)
async def decisions_by_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    records = await ModelRoutingService(db).decisions(run_id=run_id)
    return ApiResponse(data=records, meta={"total": len(records)})


@router.post("/usage", response_model=ApiResponse)
async def log_usage(body: ModelUsageCreate, db: AsyncSession = Depends(get_db)):
    item = await ModelUsageLogger(db).log(body)
    await db.commit()
    return ApiResponse(data=item)


@router.get("/usage", response_model=ApiResponse)
async def usage(
    stack_run_id: uuid.UUID | None = None, limit: int = Query(200, ge=1, le=1000), db: AsyncSession = Depends(get_db)
):
    records = await ModelUsageLogger(db).list(stack_run_id, limit)
    return ApiResponse(data=records, meta={"total": len(records)})


@router.get("/usage/summary", response_model=ApiResponse)
async def usage_summary(db: AsyncSession = Depends(get_db)):
    return ApiResponse(data=await ModelUsageLogger(db).summary())


@router.get("/usage/by-stack/{stack_run_id}", response_model=ApiResponse)
async def usage_by_stack(stack_run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    records = await ModelUsageLogger(db).list(stack_run_id)
    return ApiResponse(data=records, meta={"total": len(records)})


@router.get("/routing/task-types", response_model=ApiResponse)
async def task_types():
    return ApiResponse(data=list(TASK_TYPES))
