"""Governed lifecycle API for enterprise transformation profiles."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.schemas.common import ApiResponse
from shogun.schemas.transformation_profile import (
    PrivateTransformationProfileExportRequest,
    PrivateTransformationProfileImportRequest,
    TransformationProfileCandidateCreate,
    TransformationProfilePromotionRequest,
    TransformationProfileRetireRequest,
    TransformationProfileRollbackRequest,
    TransformationProfileValidationRequest,
)
from shogun.services.private_transformation_profiles import (
    PrivateTransformationProfileError,
    PrivateTransformationProfileService,
)
from shogun.services.transformation_profile_registry import (
    ProtectedTransformationProfileError,
    TransformationAdapterUnavailableError,
    TransformationProfileLifecycleError,
    TransformationProfileNotFoundError,
    TransformationProfileRegistryError,
    TransformationProfileRegistryService,
)

router = APIRouter(prefix="/transformation-profiles", tags=["Transformation profiles"])


def _http_error(exc: TransformationProfileRegistryError) -> HTTPException:
    if isinstance(exc, TransformationProfileNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, ProtectedTransformationProfileError):
        return HTTPException(403, str(exc))
    if isinstance(exc, (TransformationAdapterUnavailableError, TransformationProfileLifecycleError)):
        return HTTPException(409, str(exc))
    return HTTPException(422, str(exc))


@router.post("/private-files/export", response_model=ApiResponse)
async def export_private_transformation_profile(
    body: PrivateTransformationProfileExportRequest,
    db: AsyncSession = Depends(get_db),
):
    """Validate an inline profile and return a portable, non-registry file."""

    try:
        data = await PrivateTransformationProfileService().export_profile_reference(
            body.profile,
            registry_service=TransformationProfileRegistryService(db),
            execution_mode=body.execution_mode,
            display_name=body.display_name,
        )
    except TransformationProfileRegistryError as exc:
        raise _http_error(exc) from exc
    except (PrivateTransformationProfileError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return ApiResponse(data=data)


@router.post("/private-files/import", response_model=ApiResponse)
async def import_private_transformation_profile(
    body: PrivateTransformationProfileImportRequest,
):
    """Validate a portable file and return a flow-local profile reference."""

    try:
        data = PrivateTransformationProfileService().import_document(body.document)
    except (PrivateTransformationProfileError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc
    return ApiResponse(data=data)


@router.get("/adapters", response_model=ApiResponse)
async def list_transformation_adapters(db: AsyncSession = Depends(get_db)):
    service = TransformationProfileRegistryService(db)
    records = await service.list_adapters()
    return ApiResponse(data=records, meta={"total": len(records)})


@router.post("/sync-bundled", response_model=ApiResponse)
async def repair_bundled_transformation_profiles(db: AsyncSession = Depends(get_db)):
    """Re-seed protected package profiles without replacing learned actives."""

    service = TransformationProfileRegistryService(db)
    try:
        stats = await service.sync_bundled_profiles()
        await db.commit()
    except TransformationProfileRegistryError as exc:
        await db.rollback()
        raise _http_error(exc) from exc
    return ApiResponse(data=stats)


@router.get("", response_model=ApiResponse)
async def list_transformation_profiles(
    lifecycle: str | None = Query(default=None, max_length=30),
    platform: str | None = Query(default=None, max_length=100),
    db: AsyncSession = Depends(get_db),
):
    service = TransformationProfileRegistryService(db)
    try:
        records = await service.list_profiles(lifecycle=lifecycle, platform=platform)
    except TransformationProfileRegistryError as exc:
        raise _http_error(exc) from exc
    return ApiResponse(data=records, meta={"total": len(records)})


@router.post("/candidates", response_model=ApiResponse, status_code=201)
async def create_transformation_profile_candidate(
    body: TransformationProfileCandidateCreate,
    db: AsyncSession = Depends(get_db),
):
    service = TransformationProfileRegistryService(db)
    try:
        version = await service.create_candidate(body)
        await db.commit()
        await db.refresh(version)
        data = await service.version_data(version)
    except TransformationProfileRegistryError as exc:
        await db.rollback()
        raise _http_error(exc) from exc
    return ApiResponse(data=data)


@router.post("/versions/{version_id}/validate", response_model=ApiResponse)
async def validate_transformation_profile_candidate(
    version_id: uuid.UUID,
    body: TransformationProfileValidationRequest,
    db: AsyncSession = Depends(get_db),
):
    service = TransformationProfileRegistryService(db)
    try:
        version = await service.validate_candidate(version_id, body)
        await db.commit()
        data = await service.version_data(version)
    except TransformationProfileRegistryError as exc:
        await db.rollback()
        raise _http_error(exc) from exc
    return ApiResponse(data=data)


@router.post("/versions/{version_id}/promote", response_model=ApiResponse)
async def promote_transformation_profile_version(
    version_id: uuid.UUID,
    body: TransformationProfilePromotionRequest,
    db: AsyncSession = Depends(get_db),
):
    service = TransformationProfileRegistryService(db)
    try:
        version = await service.promote(version_id, actor=body.actor)
        await db.commit()
        data = await service.version_data(version)
    except TransformationProfileRegistryError as exc:
        await db.rollback()
        raise _http_error(exc) from exc
    return ApiResponse(data=data)


@router.post("/versions/{version_id}/retire", response_model=ApiResponse)
async def retire_transformation_profile_version(
    version_id: uuid.UUID,
    body: TransformationProfileRetireRequest,
    db: AsyncSession = Depends(get_db),
):
    service = TransformationProfileRegistryService(db)
    try:
        version = await service.retire(
            version_id,
            actor=body.actor,
            reason=body.reason,
        )
        await db.commit()
        data = await service.version_data(version)
    except TransformationProfileRegistryError as exc:
        await db.rollback()
        raise _http_error(exc) from exc
    return ApiResponse(data=data)


@router.post("/{profile_id}/rollback", response_model=ApiResponse)
async def rollback_transformation_profile(
    profile_id: str,
    body: TransformationProfileRollbackRequest,
    db: AsyncSession = Depends(get_db),
):
    service = TransformationProfileRegistryService(db)
    try:
        version = await service.rollback(
            profile_id,
            target_version=body.target_version,
            actor=body.actor,
        )
        await db.commit()
        data = await service.version_data(version)
    except TransformationProfileRegistryError as exc:
        await db.rollback()
        raise _http_error(exc) from exc
    return ApiResponse(data=data)


@router.get("/{profile_id}", response_model=ApiResponse)
async def get_transformation_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = TransformationProfileRegistryService(db)
    try:
        profile = await service.get_profile(profile_id)
        data = await service.profile_data(profile)
    except TransformationProfileRegistryError as exc:
        raise _http_error(exc) from exc
    return ApiResponse(data=data)


@router.delete("/{profile_id}", response_model=ApiResponse)
async def delete_transformation_profile(
    profile_id: str,
    actor: str = Query(default="system", min_length=1, max_length=255),
    db: AsyncSession = Depends(get_db),
):
    service = TransformationProfileRegistryService(db)
    try:
        await service.delete_profile(profile_id, actor=actor)
        await db.commit()
    except TransformationProfileRegistryError as exc:
        await db.rollback()
        raise _http_error(exc) from exc
    return ApiResponse(data={"profile_id": profile_id, "deleted": True})
