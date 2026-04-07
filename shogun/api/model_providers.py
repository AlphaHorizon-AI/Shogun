"""Model provider and routing routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_model_provider_service, get_model_routing_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.models import (
    ModelProviderCreate,
    ModelProviderResponse,
    ModelProviderUpdate,
    ModelRoutingProfileCreate,
    ModelRoutingProfileResponse,
    ModelRoutingProfileUpdate,
)
from shogun.services.model_service import ModelProviderService, ModelRoutingProfileService

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
    return ApiResponse(data=ModelProviderResponse.model_validate(record))


@provider_router.patch("/{provider_id}", response_model=ApiResponse)
async def update_provider(
    provider_id: uuid.UUID,
    body: ModelProviderUpdate,
    svc: ModelProviderService = Depends(get_model_provider_service),
):
    record = await svc.update(provider_id, **body.model_dump(exclude_unset=True))
    if not record:
        raise HTTPException(status_code=404, detail="Provider not found")
    return ApiResponse(data=ModelProviderResponse.model_validate(record))


@provider_router.post("/{provider_id}/test", response_model=ApiResponse)
async def test_provider(provider_id: uuid.UUID):
    return ApiResponse(data={"status": "test_not_implemented", "provider_id": str(provider_id)})


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


router.include_router(provider_router)
router.include_router(routing_router)
