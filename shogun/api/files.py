"""HTTP surface for deterministic file format adapters."""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.api.deps import get_db
from shogun.config import settings
from shogun.schemas.file_formats import (
    ArchiveExtractRequest,
    FileCompareRequest,
    FileIndexRequest,
    FileQueryRequest,
    FileReferenceRequest,
    FileTransformRequest,
)
from shogun.services.file_formats import FileFormatError, FileFormatService, registry

router = APIRouter(prefix="/files", tags=["File Formats"])


def _service(db: AsyncSession = Depends(get_db)) -> FileFormatService:
    return FileFormatService(db)


def _reference(body: FileReferenceRequest) -> dict:
    return {"path": body.path, "file_id": body.file_id, "source": body.source, "mime_type": body.mime_type}


def _raise(exc: FileFormatError) -> None:
    code = (
        404
        if exc.error_type == "not_found"
        else 403
        if exc.error_type in {"path_escape", "path_outside_workspace", "policy_blocked", "blocked_file_type"}
        else 422
    )
    raise HTTPException(status_code=code, detail={"error_type": exc.error_type, "message": str(exc)}) from exc


@router.get("/formats")
async def supported_formats():
    return {"data": registry.formats()}


@router.post("/register")
async def register_upload(
    file: UploadFile = File(...), source: str = "chat", svc: FileFormatService = Depends(_service)
):
    try:
        settings.uploads_path.mkdir(parents=True, exist_ok=True)
        safe_name = Path(file.filename or "upload").name
        destination = settings.uploads_path / f"{uuid.uuid4().hex[:12]}-{safe_name}"
        total = 0
        with destination.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > settings.file_max_parse_bytes:
                    output.close()
                    destination.unlink(missing_ok=True)
                    raise FileFormatError("Upload exceeds the configured file size limit.", "file_too_large")
                output.write(chunk)
        result = await svc.inspect(path=str(destination), source=source, mime_type=file.content_type)
        await svc.session.commit()
        return {"data": result}
    except FileFormatError as exc:
        await svc.session.rollback()
        _raise(exc)


@router.post("/detect")
async def detect_file(body: FileReferenceRequest, svc: FileFormatService = Depends(_service)):
    try:
        return {"data": await svc.detect(body.path, body.file_id, body.mime_type)}
    except FileFormatError as exc:
        _raise(exc)


@router.post("/inspect")
async def inspect_file(body: FileReferenceRequest, svc: FileFormatService = Depends(_service)):
    try:
        result = await svc.inspect(**_reference(body))
        await svc.session.commit()
        return {"data": result}
    except FileFormatError as exc:
        await svc.session.rollback()
        _raise(exc)


@router.post("/preview")
async def preview_file(body: FileReferenceRequest, svc: FileFormatService = Depends(_service)):
    response = await inspect_file(body, svc)
    data = response["data"]
    return {
        "data": {
            key: data[key]
            for key in ("status", "file_id", "format_id", "summary", "preview", "warnings", "audit_event_id")
        }
    }


@router.post("/schema")
async def file_schema(body: FileReferenceRequest, svc: FileFormatService = Depends(_service)):
    response = await inspect_file(body, svc)
    data = response["data"]
    return {
        "data": {
            "file_id": data["file_id"],
            "format_id": data["format_id"],
            "schema": data["schema"],
            "summary": data["summary"],
        }
    }


@router.post("/query")
async def query_file(body: FileQueryRequest, svc: FileFormatService = Depends(_service)):
    try:
        return {"data": await svc.query(body.query, body.path, body.file_id, body.limit)}
    except FileFormatError as exc:
        _raise(exc)


@router.post("/validate")
async def validate_file(body: FileReferenceRequest, svc: FileFormatService = Depends(_service)):
    return {"data": await svc.validate(**_reference(body))}


@router.post("/transform")
@router.post("/export")
async def transform_file(body: FileTransformRequest, svc: FileFormatService = Depends(_service)):
    try:
        return {"data": await svc.transform(body.target_format, body.output_filename, body.options, **_reference(body))}
    except FileFormatError as exc:
        _raise(exc)


@router.post("/compare")
async def compare_files(body: FileCompareRequest, svc: FileFormatService = Depends(_service)):
    try:
        result = await svc.compare(body.left_path, body.right_path)
        await svc.session.commit()
        return {"data": result}
    except FileFormatError as exc:
        await svc.session.rollback()
        _raise(exc)


@router.post("/index")
async def index_file_profile(body: FileIndexRequest, svc: FileFormatService = Depends(_service)):
    try:
        return {"data": await svc.index_profile(body.agent_id, body.title, **_reference(body))}
    except FileFormatError as exc:
        await svc.session.rollback()
        _raise(exc)


@router.post("/archive/inspect")
async def inspect_archive(body: FileReferenceRequest, svc: FileFormatService = Depends(_service)):
    return await inspect_file(body, svc)


@router.post("/archive/extract-selected")
async def extract_archive(body: ArchiveExtractRequest, svc: FileFormatService = Depends(_service)):
    try:
        return {
            "data": await svc.extract_archive(
                body.members,
                body.output_directory,
                body.allow_overwrite,
                body.approved,
                **_reference(body),
            )
        }
    except FileFormatError as exc:
        _raise(exc)


@router.post("/code/outline")
@router.post("/code/symbols")
async def code_outline(body: FileReferenceRequest, svc: FileFormatService = Depends(_service)):
    response = await inspect_file(body, svc)
    data = response["data"]
    if data["format_id"] != "code":
        raise HTTPException(status_code=422, detail="Selected file is not recognized as source code.")
    return {
        "data": {
            "file_id": data["file_id"],
            "format_id": "code",
            "language": data["data"].get("language"),
            "symbols": data["data"].get("symbols", []),
            "imports": data["data"].get("imports", []),
        }
    }


@router.get("/{file_id}/capabilities")
async def file_capabilities(file_id: uuid.UUID, svc: FileFormatService = Depends(_service)):
    try:
        artifact = await svc.get_artifact(file_id)
        return {
            "data": {
                "file_id": str(file_id),
                "format_id": artifact["format_id"],
                "capabilities": artifact["capabilities"],
            }
        }
    except FileFormatError as exc:
        _raise(exc)


@router.get("/{file_id}")
async def get_file(file_id: uuid.UUID, svc: FileFormatService = Depends(_service)):
    try:
        return {"data": await svc.get_artifact(file_id)}
    except FileFormatError as exc:
        _raise(exc)
