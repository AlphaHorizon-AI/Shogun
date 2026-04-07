"""Memory API routes — search, CRUD, reinforcement, and salience."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from shogun.api.deps import get_memory_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.memory import (
    MemoryRecordCreate,
    MemoryRecordResponse,
    MemoryRecordUpdate,
    MemoryReinforcementRequest,
    MemorySearchRequest,
    MemorySearchResponse,
)
from shogun.services.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["Memory"])


@router.post("/search", response_model=ApiResponse)
async def search_memory(body: MemorySearchRequest):
    """Search memory via vector similarity + salience reranking.

    Phase 2 will integrate Qdrant. Currently returns empty results.
    """
    return ApiResponse(
        data=MemorySearchResponse(results=[]).model_dump(),
        meta={"note": "Qdrant vector search integration pending (Phase 2)"},
    )


@router.get("/{memory_id}", response_model=ApiResponse)
async def get_memory(
    memory_id: uuid.UUID,
    svc: MemoryService = Depends(get_memory_service),
):
    record = await svc.get_by_id(memory_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return ApiResponse(data=MemoryRecordResponse.model_validate(record))


@router.post("", response_model=ApiResponse, status_code=201)
async def create_memory(
    body: MemoryRecordCreate,
    svc: MemoryService = Depends(get_memory_service),
):
    data = body.model_dump()
    # Remove tags for now (stored in Qdrant payload in Phase 2)
    data.pop("tags", None)
    record = await svc.create(**data)
    return ApiResponse(data=MemoryRecordResponse.model_validate(record))


@router.patch("/{memory_id}", response_model=ApiResponse)
async def update_memory(
    memory_id: uuid.UUID,
    body: MemoryRecordUpdate,
    svc: MemoryService = Depends(get_memory_service),
):
    record = await svc.update(memory_id, **body.model_dump(exclude_unset=True))
    if not record:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return ApiResponse(data=MemoryRecordResponse.model_validate(record))


@router.post("/{memory_id}/forget", response_model=ApiResponse)
async def forget_memory(
    memory_id: uuid.UUID,
    svc: MemoryService = Depends(get_memory_service),
):
    record = await svc.update(memory_id, is_archived=True)
    if not record:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return ApiResponse(data={"forgotten": True, "memory_id": str(memory_id)})


@router.post("/reinforce", response_model=ApiResponse)
async def reinforce_memory(
    body: MemoryReinforcementRequest,
    svc: MemoryService = Depends(get_memory_service),
):
    """Report a reinforcement or penalty event for a memory.

    Events:
    - retrieved_and_used: Memory contributed to output
    - confirmed_by_operator: Operator confirmed usefulness
    - reused_across_sessions: Successfully reused across sessions
    - retrieved_not_used: Retrieved as candidate but not used (mild penalty)
    """
    record = await svc.reinforce(
        memory_id=body.memory_id,
        event_type=body.event_type,
        strength=body.strength,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return ApiResponse(data=MemoryRecordResponse.model_validate(record))


@router.get("/{memory_id}/effective-relevance", response_model=ApiResponse)
async def get_effective_relevance(
    memory_id: uuid.UUID,
    svc: MemoryService = Depends(get_memory_service),
):
    """Get the current effective relevance score with decay applied."""
    relevance = await svc.get_effective_relevance(memory_id)
    if relevance is None:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return ApiResponse(data={"memory_id": str(memory_id), "effective_relevance": relevance})


@router.post("/decay/apply", response_model=ApiResponse)
async def apply_decay(
    agent_id: uuid.UUID | None = None,
    svc: MemoryService = Depends(get_memory_service),
):
    """Apply time-based decay to memory records (Bushido hook)."""
    updated = await svc.apply_decay_batch(agent_id=agent_id)
    return ApiResponse(data={"records_updated": updated})
