"""Persona routes — CRUD for behavioral profiles."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_persona_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.personas import PersonaCreate, PersonaResponse, PersonaUpdate
from shogun.services.persona_service import PersonaService

router = APIRouter(prefix="/personas", tags=["Personas"])


@router.get("", response_model=ApiResponse)
async def list_personas(
    builtin_only: bool = False,
    active_only: bool = True,
    svc: PersonaService = Depends(get_persona_service),
):
    filters = []
    from shogun.db.models.persona import Persona

    if builtin_only:
        filters.append(Persona.is_builtin == True)
    if active_only:
        filters.append(Persona.is_active == True)

    records, total = await svc.get_all(filters=filters)
    return ApiResponse(
        data=[PersonaResponse.model_validate(r) for r in records],
        meta={"total": total},
    )


@router.get("/{persona_id}", response_model=ApiResponse)
async def get_persona(
    persona_id: uuid.UUID,
    svc: PersonaService = Depends(get_persona_service),
):
    record = await svc.get_by_id(persona_id)
    if not record:
        raise HTTPException(status_code=404, detail="Persona not found")
    return ApiResponse(data=PersonaResponse.model_validate(record))


@router.post("", response_model=ApiResponse, status_code=201)
async def create_persona(
    body: PersonaCreate,
    svc: PersonaService = Depends(get_persona_service),
):
    record = await svc.create(**body.model_dump())
    return ApiResponse(data=PersonaResponse.model_validate(record))


@router.patch("/{persona_id}", response_model=ApiResponse)
async def update_persona(
    persona_id: uuid.UUID,
    body: PersonaUpdate,
    svc: PersonaService = Depends(get_persona_service),
):
    record = await svc.update(persona_id, **body.model_dump(exclude_unset=True))
    if not record:
        raise HTTPException(status_code=404, detail="Persona not found")
    return ApiResponse(data=PersonaResponse.model_validate(record))


@router.delete("/{persona_id}", response_model=ApiResponse)
async def delete_persona(
    persona_id: uuid.UUID,
    svc: PersonaService = Depends(get_persona_service),
):
    deleted = await svc.delete(persona_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Persona not found")
    return ApiResponse(data={"deleted": True})
