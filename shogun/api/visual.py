"""Visual intake API for chat, Telegram, agents, and Flow Stacks."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.services.event_logger import EventLogger
from shogun.services.visual_intake import VisualIntakeError, VisualIntakeService

router = APIRouter(prefix="/visual", tags=["Visual Intake"])


def _svc(db: AsyncSession = Depends(get_db)) -> VisualIntakeService:
    return VisualIntakeService(db)


@router.post("/intake")
async def intake_image(
    file: UploadFile = File(...),
    caption: str | None = Form(None),
    chat_session_id: str | None = Form(None),
    source: str = Form("chat"),
    svc: VisualIntakeService = Depends(_svc),
):
    try:
        if not (await svc.permissions()).get("allow_image_intake", True):
            raise VisualIntakeError("Image intake is disabled by the Shogun visual intake policy.")
        artifact = await svc.ingest(
            await file.read(),
            filename=file.filename or "image",
            declared_mime=file.content_type,
            source=source,
            caption=caption,
            chat_session_id=chat_session_id,
        )
        await svc.session.commit()
        await EventLogger.emit(
            "visual",
            "visual.intake",
            f"Stored image artifact {artifact.id}",
            detail={
                "artifact_id": str(artifact.id),
                "source": source,
                "mime_type": artifact.mime_type,
                "byte_size": artifact.byte_size,
            },
        )
        return {"data": svc._public(artifact)}
    except VisualIntakeError as exc:
        await svc.session.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/recent")
async def recent_images(limit: int = 30, chat_session_id: str | None = None, svc: VisualIntakeService = Depends(_svc)):
    return {"data": [svc._public(item) for item in await svc.recent(limit, chat_session_id)]}


async def _artifact_or_404(artifact_id: uuid.UUID, svc: VisualIntakeService):
    artifact = await svc.get(artifact_id)
    if not artifact:
        raise HTTPException(status_code=404, detail="Image artifact not found.")
    return artifact


@router.get("/{artifact_id}/content")
async def image_content(artifact_id: uuid.UUID, svc: VisualIntakeService = Depends(_svc)):
    artifact = await _artifact_or_404(artifact_id, svc)
    path = Path(artifact.normalized_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Image file is unavailable.")
    return FileResponse(path, media_type="image/webp", filename=artifact.original_filename)


@router.get("/{artifact_id}/thumbnail")
async def image_thumbnail(artifact_id: uuid.UUID, svc: VisualIntakeService = Depends(_svc)):
    artifact = await _artifact_or_404(artifact_id, svc)
    path = Path(artifact.thumbnail_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Thumbnail is unavailable.")
    return FileResponse(path, media_type="image/webp")


@router.get("/{artifact_id}")
async def image_metadata(artifact_id: uuid.UUID, svc: VisualIntakeService = Depends(_svc)):
    return {"data": svc._public(await _artifact_or_404(artifact_id, svc))}


@router.post("/{artifact_id}/describe")
async def describe_image(artifact_id: uuid.UUID, body: dict | None = None, svc: VisualIntakeService = Depends(_svc)):
    artifact = await _artifact_or_404(artifact_id, svc)
    body = body or {}
    try:
        analysis = await svc.analyze(
            artifact,
            str(body.get("prompt") or "Describe this image accurately, including visible text and important details."),
            "describe",
            bool(body.get("allow_cloud", False)),
        )
        await svc.session.commit()
        await EventLogger.emit(
            "visual",
            "visual.analyze",
            f"Analyzed image artifact {artifact.id}",
            model_used=analysis.model_used,
            provider_used=analysis.provider_used,
            detail={"artifact_id": str(artifact.id), "analysis_type": "describe"},
        )
        return {
            "data": {
                "id": str(analysis.id),
                "result": analysis.result_text,
                "model": analysis.model_used,
                "provider": analysis.provider_used,
            }
        }
    except VisualIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{artifact_id}/inspect")
async def inspect_image(artifact_id: uuid.UUID, body: dict, svc: VisualIntakeService = Depends(_svc)):
    artifact = await _artifact_or_404(artifact_id, svc)
    prompt = str(body.get("prompt") or "Inspect the image in detail and answer with evidence from the image.")
    try:
        analysis = await svc.analyze(artifact, prompt, "inspect", bool(body.get("allow_cloud", False)))
        await svc.session.commit()
        return {
            "data": {
                "id": str(analysis.id),
                "result": analysis.result_text,
                "model": analysis.model_used,
                "provider": analysis.provider_used,
            }
        }
    except VisualIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{artifact_id}/extract-text")
async def extract_image_text(
    artifact_id: uuid.UUID, body: dict | None = None, svc: VisualIntakeService = Depends(_svc)
):
    if not (await svc.permissions()).get("allow_ocr", True):
        raise HTTPException(status_code=403, detail="Image text extraction is disabled by policy.")
    artifact = await _artifact_or_404(artifact_id, svc)
    try:
        analysis = await svc.analyze(
            artifact,
            str(
                (body or {}).get("prompt")
                or "Transcribe all visible text faithfully. Preserve headings, lists, tables, and reading order."
            ),
            "extract_text",
            bool((body or {}).get("allow_cloud", False)),
        )
        await svc.session.commit()
        return {"data": {"id": str(analysis.id), "result": analysis.result_text, "model": analysis.model_used}}
    except VisualIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/compare")
async def compare_images(body: dict, svc: VisualIntakeService = Depends(_svc)):
    try:
        first = await svc.get(uuid.UUID(str(body.get("first_artifact_id"))))
        second = await svc.get(uuid.UUID(str(body.get("second_artifact_id"))))
    except (TypeError, ValueError):
        first = second = None
    if not first or not second:
        raise HTTPException(status_code=404, detail="Both image artifacts are required.")
    try:
        analysis = await svc.compare(
            first,
            second,
            str(body.get("prompt") or "Compare these images. Explain material similarities and differences."),
            bool(body.get("allow_cloud", False)),
        )
        await svc.session.commit()
        return {"data": {"id": str(analysis.id), "result": analysis.result_text, "model": analysis.model_used}}
    except VisualIntakeError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/{artifact_id}/pin")
async def pin_image(artifact_id: uuid.UUID, body: dict | None = None, svc: VisualIntakeService = Depends(_svc)):
    artifact = await _artifact_or_404(artifact_id, svc)
    artifact.pinned = bool((body or {}).get("pinned", True))
    await svc.session.commit()
    return {"data": svc._public(artifact)}


@router.delete("/{artifact_id}")
async def delete_image(artifact_id: uuid.UUID, svc: VisualIntakeService = Depends(_svc)):
    artifact = await _artifact_or_404(artifact_id, svc)
    try:
        await svc.delete(artifact)
    except VisualIntakeError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    await svc.session.commit()
    await EventLogger.emit(
        "visual", "visual.delete", f"Deleted image artifact {artifact.id}", detail={"artifact_id": str(artifact.id)}
    )
    return {"data": {"deleted": True, "artifact_id": str(artifact.id)}}


@router.post("/maintenance/cleanup")
async def cleanup_images(svc: VisualIntakeService = Depends(_svc)):
    count = await svc.cleanup_expired()
    await svc.session.commit()
    return {"data": {"removed": count}}
