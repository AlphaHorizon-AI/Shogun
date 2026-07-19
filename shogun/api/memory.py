"""Memory API routes — search, CRUD, reinforcement, and salience."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from shogun.api.deps import get_memory_service
from shogun.schemas.common import ApiResponse, DecayClass
from shogun.schemas.memory import (
    MemoryExportJobResponse,
    MemoryExportPreview,
    MemoryExportRequest,
    MemoryImportBatchResponse,
    MemoryImportConfirmRequest,
    MemoryRecordCreate,
    MemoryRecordResponse,
    MemoryRecordUpdate,
    MemoryReinforcementRequest,
    MemorySearchRequest,
)
from shogun.services.memory_export_service import MemoryExportService, job_response
from shogun.services.memory_import_service import MemoryImportService, batch_response
from shogun.services.memory_service import MemoryService

router = APIRouter(prefix="/memory", tags=["Memory"])


def _programming_archive_record(record) -> dict:
    """Present project memory in the common Archive card shape plus IDE metadata."""
    from shogun.services.programming_memory import ProgrammingMemoryService

    data = ProgrammingMemoryService.serialize(record)
    importance = {
        "production_confirmed": 1.0,
        "tests_passed": 0.9,
        "operator_confirmed": 0.8,
        "unverified": 0.5,
    }.get(record.validation_status, 0.5)
    return {
        **data,
        "memory_type": "programming",
        "content": record.solution,
        "summary": record.problem,
        "relevance_score": record.confidence_score,
        "importance_score": importance,
        "decay_class": "project-scoped",
        "is_pinned": False,
        "access_count": record.use_count,
        "recall_count": record.use_count,
        "last_accessed_at": record.last_used_at,
        "last_confirmed_at": record.last_used_at,
        "is_archived": False,
    }


# ── Stats ────────────────────────────────────────────────────

@router.get("/stats", response_model=ApiResponse)
async def memory_stats(
    svc: MemoryService = Depends(get_memory_service),
):
    """Get aggregate memory statistics for the Archives sidebar."""
    from sqlalchemy import func, select

    from shogun.db.models.memory_record import MemoryRecord

    session = svc.session

    # Total active (non-archived) records
    total_result = await session.execute(
        select(func.count(MemoryRecord.id)).where(MemoryRecord.is_archived.is_(False))
    )
    total_active = total_result.scalar() or 0

    # Total archived
    archived_result = await session.execute(
        select(func.count(MemoryRecord.id)).where(MemoryRecord.is_archived.is_(True))
    )
    total_archived = archived_result.scalar() or 0

    # Per-type counts
    type_result = await session.execute(
        select(MemoryRecord.memory_type, func.count(MemoryRecord.id))
        .where(MemoryRecord.is_archived.is_(False))
        .group_by(MemoryRecord.memory_type)
    )
    type_counts = {r[0]: r[1] for r in type_result.all()}

    # Programming memory deliberately lives in a project-scoped table, but it
    # is still operator-visible memory and therefore belongs in Archive totals.
    from shogun.db.models.programming_memory import ProgrammingMemory

    programming_count = (
        await session.scalar(select(func.count(ProgrammingMemory.id)))
    ) or 0
    total_active += programming_count
    type_counts["programming"] = programming_count

    # Retention rate = active / (active + archived) * 100
    grand_total = total_active + total_archived
    retention_rate = round((total_active / grand_total * 100), 1) if grand_total > 0 else 100.0

    # Pinned count
    pinned_result = await session.execute(
        select(func.count(MemoryRecord.id)).where(
            MemoryRecord.is_pinned.is_(True),
            MemoryRecord.is_archived.is_(False),
        )
    )
    pinned_count = pinned_result.scalar() or 0

    # Avg relevance score
    avg_result = await session.execute(
        select(func.avg(MemoryRecord.relevance_score)).where(MemoryRecord.is_archived.is_(False))
    )
    avg_relevance = round(avg_result.scalar() or 0.0, 3)

    # Avg importance
    avg_imp = await session.execute(
        select(func.avg(MemoryRecord.importance_score)).where(MemoryRecord.is_archived.is_(False))
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


# ── Project-scoped programming memory ─────────────────────────────────────


@router.get("/programming", response_model=ApiResponse)
async def list_programming_memories(
    query: str | None = None,
    workspace_key: str | None = None,
    agent_id: uuid.UUID | None = None,
    kind: str | None = None,
    validation_status: str | None = None,
    sort_by: str = Query("created_at"),
    limit: int = Query(200, ge=1, le=500),
    svc: MemoryService = Depends(get_memory_service),
):
    """List evidence-aware IDE memories for the Programming Archive category."""
    from sqlalchemy import case, or_, select

    from shogun.db.models.programming_memory import ProgrammingMemory

    filters = []
    if workspace_key:
        filters.append(ProgrammingMemory.workspace_key == workspace_key)
    if agent_id:
        filters.append(ProgrammingMemory.agent_id == agent_id)
    if kind:
        filters.append(ProgrammingMemory.kind == kind)
    if validation_status:
        filters.append(ProgrammingMemory.validation_status == validation_status)
    if query and query.strip():
        term = f"%{query.strip()}%"
        filters.append(
            or_(
                ProgrammingMemory.title.ilike(term),
                ProgrammingMemory.problem.ilike(term),
                ProgrammingMemory.solution.ilike(term),
                ProgrammingMemory.evidence.ilike(term),
                ProgrammingMemory.workspace_name.ilike(term),
            )
        )

    order = ProgrammingMemory.created_at.desc()
    if sort_by == "relevance":
        order = ProgrammingMemory.confidence_score.desc()
    elif sort_by == "importance":
        order = case(
            (ProgrammingMemory.validation_status == "production_confirmed", 4),
            (ProgrammingMemory.validation_status == "tests_passed", 3),
            (ProgrammingMemory.validation_status == "operator_confirmed", 2),
            (ProgrammingMemory.validation_status == "unverified", 1),
            else_=0,
        ).desc()

    statement = select(ProgrammingMemory).where(*filters).order_by(order).limit(limit)
    records = list((await svc.session.scalars(statement)).all())
    return ApiResponse(
        data=[_programming_archive_record(record) for record in records],
        meta={"total": len(records)},
    )


@router.delete("/programming/{memory_id}", response_model=ApiResponse)
async def delete_programming_memory(
    memory_id: uuid.UUID,
    svc: MemoryService = Depends(get_memory_service),
):
    """Delete a programming memory after explicit operator action in Archives."""
    from shogun.db.models.programming_memory import ProgrammingMemory

    record = await svc.session.get(ProgrammingMemory, memory_id)
    if not record:
        raise HTTPException(status_code=404, detail="Programming memory not found")
    await svc.session.delete(record)
    await svc.session.commit()
    return ApiResponse(data={"deleted": True, "id": str(memory_id)})


# ── List ─────────────────────────────────────────────────────

@router.post("/skills/sync", response_model=ApiResponse)
async def sync_archives_skills(
    svc: MemoryService = Depends(get_memory_service),
):
    """Validate full Markdown and refresh every active agent's Skills layer."""
    from shogun.services.skill_memory_sync import sync_skills_to_all_agent_memories

    result = await sync_skills_to_all_agent_memories(svc.session)
    if not result["agents"]:
        raise HTTPException(status_code=404, detail="No active agents found")
    return ApiResponse(data=result)


@router.get("", response_model=ApiResponse)
async def list_memories(
    agent_id: uuid.UUID | None = None,
    memory_type: str | None = Query(None, alias="memory_type"),
    decay_class: DecayClass | None = Query(None, alias="decay_class"),
    include_archived: bool = False,
    sort_by: str = Query("created_at", alias="sort_by"),
    svc: MemoryService = Depends(get_memory_service),
):
    from shogun.db.models.memory_record import MemoryRecord
    filters = []
    if not include_archived:
        filters.append(MemoryRecord.is_archived.is_(False))
    if agent_id:
        filters.append(MemoryRecord.agent_id == agent_id)
    if memory_type:
        filters.append(MemoryRecord.memory_type == memory_type)
    if decay_class:
        filters.append(MemoryRecord.decay_class == decay_class.value)

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
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    try:
        results = await svc.search(
            query=body.query,
            agent_id=body.agent_id,
            memory_types=[t.value for t in body.memory_types] if body.memory_types else None,
            min_importance=body.filters.min_importance if body.filters else None,
            pinned_only=body.filters.pinned_only if body.filters else False,
            decay_class=(body.filters.decay_class.value if body.filters and body.filters.decay_class else None),
            limit=body.limit,
            weight_overrides=body.weight_overrides,
        )
    except Exception as e:
        logger.error("Memory search failed: %s\n%s", e, traceback.format_exc())
        return ApiResponse(
            data=[],
            meta={"query": body.query, "count": 0, "error": str(e)},
        )

    return ApiResponse(
        data=results,
        meta={"query": body.query, "count": len(results)},
    )


# ── Order 16: Portable Markdown export ─────────────────────────────────────


@router.post("/export/preview", response_model=ApiResponse[MemoryExportPreview])
async def preview_memory_export(
    body: MemoryExportRequest,
    svc: MemoryService = Depends(get_memory_service),
):
    export_svc = MemoryExportService(svc.session)
    preview = await export_svc.preview(body)
    from shogun.services.event_logger import EventLogger

    await EventLogger.emit(
        category="memory",
        event_type="memory.export.preview_requested",
        action="Previewed portable memory export",
        user_id="local_user",
        data_classification="private" if body.include_private else "internal",
        detail={"filters": preview["filters"], "counts": preview["estimated_counts"]},
    )
    return ApiResponse(data=preview)


async def _run_memory_export(export_id: str) -> None:
    from shogun.db.engine import async_session_factory

    async with async_session_factory() as session:
        await MemoryExportService(session).execute(export_id)


@router.post("/export", response_model=ApiResponse[MemoryExportJobResponse], status_code=202)
async def start_memory_export(
    body: MemoryExportRequest,
    background_tasks: BackgroundTasks,
    svc: MemoryService = Depends(get_memory_service),
):
    export_svc = MemoryExportService(svc.session)
    try:
        job = await export_svc.create_job(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await svc.session.commit()
    background_tasks.add_task(_run_memory_export, job.id)
    return ApiResponse(data=job_response(job))


@router.get("/export/history", response_model=ApiResponse[list[MemoryExportJobResponse]])
async def memory_export_history(
    limit: int = Query(20, ge=1, le=100),
    svc: MemoryService = Depends(get_memory_service),
):
    jobs = await MemoryExportService(svc.session).history(limit)
    return ApiResponse(data=[job_response(job) for job in jobs])


@router.get("/export/{export_id}", response_model=ApiResponse[MemoryExportJobResponse])
async def memory_export_status(
    export_id: str,
    svc: MemoryService = Depends(get_memory_service),
):
    job = await MemoryExportService(svc.session).get_job(export_id)
    if not job:
        raise HTTPException(status_code=404, detail="Memory export job not found")
    return ApiResponse(data=job_response(job))


@router.post("/export/{export_id}/cancel", response_model=ApiResponse[MemoryExportJobResponse])
async def cancel_memory_export(
    export_id: str,
    svc: MemoryService = Depends(get_memory_service),
):
    try:
        job = await MemoryExportService(svc.session).cancel(export_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ApiResponse(data=job_response(job))


@router.get("/export/{export_id}/download")
async def download_memory_export(
    export_id: str,
    svc: MemoryService = Depends(get_memory_service),
):
    export_svc = MemoryExportService(svc.session)
    job = await export_svc.get_job(export_id)
    if not job:
        raise HTTPException(status_code=404, detail="Memory export job not found")
    try:
        path = export_svc.download_path(job)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    from shogun.services.event_logger import EventLogger

    await EventLogger.emit(
        category="memory",
        event_type="memory.export.downloaded",
        action=f"Downloaded memory export {export_id}",
        user_id="local_user",
        data_classification="private" if (job.filters_json or {}).get("include_private") else "internal",
        detail={"export_id": export_id, "counts": job.counts_json},
    )
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"shogun_memory_export_{export_id}.zip",
        headers={"Cache-Control": "no-store"},
    )


# ── Order 17: OpenClaw Markdown import ─────────────────────────


@router.post("/import/openclaw/preview", response_model=ApiResponse[MemoryImportBatchResponse])
async def preview_memory_import(
    files: list[UploadFile] | None = File(None),
    folder_path: str | None = Form(None),
    agent_id: uuid.UUID = Form(...),
    source_type: str = Form("openclaw"),
    default_memory_type: str = Form("semantic"),
    default_importance: int = Form(5, ge=1, le=10),
    default_decay_type: str = Form("medium"),
    svc: MemoryService = Depends(get_memory_service),
):
    """Parse and persist a mandatory preview without writing native memories."""
    importer = MemoryImportService(svc.session)
    try:
        kwargs = {
            "agent_id": agent_id,
            "source_type": source_type,
            "default_memory_type": default_memory_type,
            "default_importance": default_importance,
            "default_decay_type": default_decay_type,
        }
        if folder_path:
            from pathlib import Path

            batch = await importer.preview_folder(Path(folder_path), **kwargs)
        elif files:
            uploads = [(upload.filename or "memory.md", await upload.read()) for upload in files]
            batch = await importer.preview_uploads(uploads, **kwargs)
        else:
            raise ValueError("Select at least one Markdown/ZIP file or provide a local folder path")
        await svc.session.commit()
        items = await importer._items(batch.id)
        return ApiResponse(data=batch_response(batch, items))
    except ValueError as exc:
        await svc.session.rollback()
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit(
            category="memory",
            event_type="memory.import.preview_failed",
            action="OpenClaw Markdown import preview failed",
            result="failure",
            user_id="local_user",
            detail={"error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        await svc.session.rollback()
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit(
            category="memory",
            event_type="memory.import.preview_failed",
            action="OpenClaw Markdown import preview failed",
            result="failure",
            user_id="local_user",
            detail={"error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Memory import preview failed") from exc


@router.post("/import/openclaw/confirm", response_model=ApiResponse[MemoryImportBatchResponse])
async def confirm_memory_import(
    body: MemoryImportConfirmRequest,
    svc: MemoryService = Depends(get_memory_service),
):
    importer = MemoryImportService(svc.session)
    try:
        batch = await importer.confirm(
            body.batch_preview_id,
            duplicate_policy=body.duplicate_policy,
            conflict_policy=body.conflict_policy,
        )
        await svc.session.commit()
    except LookupError as exc:
        await svc.session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        await svc.session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        await svc.session.rollback()
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit(
            category="memory",
            event_type="memory.import.batch_failed",
            action=f"Memory import batch {body.batch_preview_id} failed",
            result="failure",
            user_id="local_user",
            detail={"batch_id": body.batch_preview_id, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Memory import batch failed") from exc
    return ApiResponse(data=batch_response(batch, await importer._items(batch.id)))


@router.get("/import/batches", response_model=ApiResponse[list[MemoryImportBatchResponse]])
async def memory_import_history(
    limit: int = Query(20, ge=1, le=100),
    svc: MemoryService = Depends(get_memory_service),
):
    importer = MemoryImportService(svc.session)
    return ApiResponse(data=[batch_response(batch) for batch in await importer.history(limit)])


@router.get("/import/batches/{batch_id}", response_model=ApiResponse[MemoryImportBatchResponse])
async def memory_import_status(
    batch_id: str,
    svc: MemoryService = Depends(get_memory_service),
):
    importer = MemoryImportService(svc.session)
    batch = await importer.get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Memory import batch not found")
    return ApiResponse(data=batch_response(batch, await importer._items(batch.id)))


@router.post("/import/batches/{batch_id}/rollback", response_model=ApiResponse[MemoryImportBatchResponse])
async def rollback_memory_import(
    batch_id: str,
    svc: MemoryService = Depends(get_memory_service),
):
    importer = MemoryImportService(svc.session)
    try:
        batch = await importer.rollback(batch_id)
        await svc.session.commit()
    except LookupError as exc:
        await svc.session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        await svc.session.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        await svc.session.rollback()
        from shogun.services.event_logger import EventLogger

        await EventLogger.emit(
            category="memory",
            event_type="memory.import.rollback_failed",
            action=f"Memory import rollback {batch_id} failed",
            result="failure",
            user_id="local_user",
            detail={"batch_id": batch_id, "error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Memory import rollback failed") from exc
    return ApiResponse(data=batch_response(batch, await importer._items(batch.id)))


@router.post("/import/batches/{batch_id}/retry-embeddings", response_model=ApiResponse[MemoryImportBatchResponse])
async def retry_memory_import_embeddings(
    batch_id: str,
    svc: MemoryService = Depends(get_memory_service),
):
    importer = MemoryImportService(svc.session)
    try:
        batch = await importer.retry_embeddings(batch_id)
        await svc.session.commit()
    except LookupError as exc:
        await svc.session.rollback()
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(data=batch_response(batch, await importer._items(batch.id)))


@router.get("/import/batches/{batch_id}/report")
async def download_memory_import_report(
    batch_id: str,
    svc: MemoryService = Depends(get_memory_service),
):
    batch = await MemoryImportService(svc.session).get_batch(batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Memory import batch not found")
    return JSONResponse(
        batch.report_json or {},
        headers={
            "Content-Disposition": f'attachment; filename="memory_import_{batch_id}.json"',
            "Cache-Control": "no-store",
        },
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
    from shogun.services.event_logger import EventLogger

    await EventLogger.emit(
        category="memory",
        event_type="memory.stored",
        action=f"Stored memory '{record.title}' through memory API",
        user_id="local_user",
        memory_ids=[str(record.id)],
        detail={
            "memory_id": str(record.id),
            "memory_type": record.memory_type,
            "importance": record.importance_score,
            "decay_type": record.decay_class,
            "tags": record.tags or [],
            "source": "memory_api",
        },
        db_session=svc.session,
    )
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
