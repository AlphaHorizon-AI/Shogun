"""Memory API routes — search, CRUD, reinforcement, and salience."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query

from shogun.api.deps import get_memory_service
from shogun.schemas.common import ApiResponse
from shogun.schemas.memory import (
    MemoryRecordCreate,
    MemoryRecordResponse,
    MemoryRecordUpdate,
    MemoryReinforcementRequest,
    MemorySearchRequest,
)
from shogun.services.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["Memory"])


# ── Stats ────────────────────────────────────────────────────

@router.get("/stats", response_model=ApiResponse)
async def memory_stats(
    svc: MemoryService = Depends(get_memory_service),
):
    """Get aggregate memory statistics for the Archives sidebar."""
    from sqlalchemy import select, func
    from shogun.db.models.memory_record import MemoryRecord

    session = svc.session

    # Total active (non-archived) records
    total_result = await session.execute(
        select(func.count(MemoryRecord.id)).where(MemoryRecord.is_archived == False)
    )
    total_active = total_result.scalar() or 0

    # Total archived
    archived_result = await session.execute(
        select(func.count(MemoryRecord.id)).where(MemoryRecord.is_archived == True)
    )
    total_archived = archived_result.scalar() or 0

    # Retention rate = active / (active + archived) * 100
    grand_total = total_active + total_archived
    retention_rate = round((total_active / grand_total * 100), 1) if grand_total > 0 else 100.0

    # Per-type counts
    type_result = await session.execute(
        select(MemoryRecord.memory_type, func.count(MemoryRecord.id))
        .where(MemoryRecord.is_archived == False)
        .group_by(MemoryRecord.memory_type)
    )
    type_counts = {r[0]: r[1] for r in type_result.all()}

    # Pinned count
    pinned_result = await session.execute(
        select(func.count(MemoryRecord.id)).where(
            MemoryRecord.is_pinned == True,
            MemoryRecord.is_archived == False,
        )
    )
    pinned_count = pinned_result.scalar() or 0

    # Avg relevance score
    avg_result = await session.execute(
        select(func.avg(MemoryRecord.relevance_score)).where(MemoryRecord.is_archived == False)
    )
    avg_relevance = round(avg_result.scalar() or 0.0, 3)

    # Avg importance
    avg_imp = await session.execute(
        select(func.avg(MemoryRecord.importance_score)).where(MemoryRecord.is_archived == False)
    )
    avg_importance = round(avg_imp.scalar() or 0.0, 3)

    # Qdrant info
    try:
        from shogun.engine.vector_store import get_vector_store
        qdrant_info = get_vector_store().collection_info()
    except Exception:
        qdrant_info = {"status": "offline"}

    return ApiResponse(data={
        "total_active": total_active,
        "total_archived": total_archived,
        "retention_rate": retention_rate,
        "type_counts": type_counts,
        "pinned_count": pinned_count,
        "avg_relevance": avg_relevance,
        "avg_importance": avg_importance,
        "qdrant": qdrant_info,
    })


# ── List ─────────────────────────────────────────────────────

@router.get("", response_model=ApiResponse)
async def list_memories(
    agent_id: uuid.UUID | None = None,
    memory_type: str | None = Query(None, alias="memory_type"),
    include_archived: bool = False,
    sort_by: str = Query("created_at", alias="sort_by"),
    svc: MemoryService = Depends(get_memory_service),
):
    from sqlalchemy import desc
    from shogun.db.models.memory_record import MemoryRecord
    filters = []
    if not include_archived:
        filters.append(MemoryRecord.is_archived == False)
    if agent_id:
        filters.append(MemoryRecord.agent_id == agent_id)
    if memory_type:
        filters.append(MemoryRecord.memory_type == memory_type)
    
    records, total = await svc.get_all(filters=filters, limit=200)
    
    # Sort results
    records_list = list(records)
    if sort_by == "relevance":
        records_list.sort(key=lambda r: r.relevance_score, reverse=True)
    elif sort_by == "importance":
        records_list.sort(key=lambda r: r.importance_score, reverse=True)
    elif sort_by == "created_at":
        records_list.sort(key=lambda r: r.created_at, reverse=True)
    
    return ApiResponse(
        data=[MemoryRecordResponse.model_validate(r) for r in records_list],
        meta={"total": total},
    )


# ── Search (semantic + salience reranking) ───────────────────

@router.post("/search", response_model=ApiResponse)
async def search_memory(
    body: MemorySearchRequest,
    svc: MemoryService = Depends(get_memory_service),
):
    """Search memory via vector similarity + salience reranking.

    Flow:
      1. Embed query → Qdrant vector search → candidate IDs
      2. Fetch full metadata from SQLite
      3. Apply salience reranking (decay × importance × recency)
      4. Return scored, ranked results
    """
    results = await svc.search(
        query=body.query,
        agent_id=body.agent_id,
        memory_types=[t.value for t in body.memory_types] if body.memory_types else None,
        min_importance=body.filters.min_importance if body.filters else None,
        pinned_only=body.filters.pinned_only if body.filters else False,
        limit=body.limit,
        weight_overrides=body.weight_overrides,
    )

    return ApiResponse(
        data=results,
        meta={"query": body.query, "count": len(results)},
    )


# ── Get ──────────────────────────────────────────────────────

@router.get("/{memory_id}", response_model=ApiResponse)
async def get_memory(
    memory_id: uuid.UUID,
    svc: MemoryService = Depends(get_memory_service),
):
    record = await svc.get_by_id(memory_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return ApiResponse(data=MemoryRecordResponse.model_validate(record))


# ── Create ───────────────────────────────────────────────────

@router.post("", response_model=ApiResponse, status_code=201)
async def create_memory(
    body: MemoryRecordCreate,
    svc: MemoryService = Depends(get_memory_service),
):
    data = body.model_dump()
    tags = data.pop("tags", [])
    record = await svc.create_memory(tags=tags, **data)
    return ApiResponse(data=MemoryRecordResponse.model_validate(record))


# ── Update ───────────────────────────────────────────────────

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


# ── Forget (Archive) ─────────────────────────────────────────

@router.post("/{memory_id}/forget", response_model=ApiResponse)
async def forget_memory(
    memory_id: uuid.UUID,
    svc: MemoryService = Depends(get_memory_service),
):
    record = await svc.forget_memory(memory_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return ApiResponse(data={"forgotten": True, "memory_id": str(memory_id)})


# ── Pin / Unpin ──────────────────────────────────────────────

@router.post("/{memory_id}/pin", response_model=ApiResponse)
async def toggle_pin_memory(
    memory_id: uuid.UUID,
    svc: MemoryService = Depends(get_memory_service),
):
    """Toggle pin status for a memory record."""
    record = await svc.get_by_id(memory_id)
    if not record:
        raise HTTPException(status_code=404, detail="Memory record not found")
    
    new_pinned = not record.is_pinned
    record = await svc.update(memory_id, is_pinned=new_pinned)
    if new_pinned:
        # Pinned memories get elevated decay class
        await svc.update(memory_id, decay_class="pinned")
    return ApiResponse(data=MemoryRecordResponse.model_validate(record))


# ── Reinforce ────────────────────────────────────────────────

@router.post("/reinforce", response_model=ApiResponse)
async def reinforce_memory(
    body: MemoryReinforcementRequest,
    svc: MemoryService = Depends(get_memory_service),
):
    """Report a reinforcement or penalty event for a memory."""
    record = await svc.reinforce(
        memory_id=body.memory_id,
        event_type=body.event_type,
        strength=body.strength,
    )
    if not record:
        raise HTTPException(status_code=404, detail="Memory record not found")
    return ApiResponse(data=MemoryRecordResponse.model_validate(record))


# ── Effective Relevance ──────────────────────────────────────

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


# ── Batch Decay ──────────────────────────────────────────────

@router.post("/decay/apply", response_model=ApiResponse)
async def apply_decay(
    agent_id: uuid.UUID | None = None,
    svc: MemoryService = Depends(get_memory_service),
):
    """Apply time-based decay to memory records (Bushido hook)."""
    updated = await svc.apply_decay_batch(agent_id=agent_id)
    return ApiResponse(data={"records_updated": updated})


# ── Reindex ──────────────────────────────────────────────────

@router.post("/reindex", response_model=ApiResponse)
async def reindex_memories(
    svc: MemoryService = Depends(get_memory_service),
):
    """Rebuild the entire Qdrant vector index from SQLite data."""
    count = await svc.reindex_all()
    return ApiResponse(data={"reindexed": count})
