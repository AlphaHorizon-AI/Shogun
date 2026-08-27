"""
Shogun Backups API — Create, list, restore, and configure automatic backups.
"""

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from shogun.api.infrastructure_auth import require_infrastructure_admin
from shogun.services.backup_service import (
    create_backup,
    delete_backup,
    list_backups,
    load_settings,
    restore_backup,
    save_settings,
)

logger = logging.getLogger("shogun.api.backups")
router = APIRouter(prefix="/backups", tags=["backups"])


# ── Models ───────────────────────────────────────────────────────

class BackupSettingsUpdate(BaseModel):
    enabled: bool | None = None
    interval_hours: int | None = None
    max_backups: int | None = None
    include_vector_memory: bool | None = None
    backup_dir: str | None = None


class CreateBackupRequest(BaseModel):
    label: str | None = None


class CreateCompleteBackupRequest(BaseModel):
    label: str | None = None
    save_path: str | None = None


# ── Endpoints ────────────────────────────────────────────────────

@router.get("/settings")
async def get_backup_settings():
    """Get the current backup configuration."""
    return load_settings()


@router.put("/settings")
async def update_backup_settings(body: BackupSettingsUpdate):
    """Update backup configuration (schedule, retention, etc.)."""
    current = load_settings()

    if body.enabled is not None:
        current["enabled"] = body.enabled
    if body.interval_hours is not None:
        if body.interval_hours < 1:
            raise HTTPException(status_code=400, detail="Interval must be at least 1 hour")
        current["interval_hours"] = body.interval_hours
    if body.max_backups is not None:
        if body.max_backups < 1:
            raise HTTPException(status_code=400, detail="Must keep at least 1 backup")
        current["max_backups"] = body.max_backups
    if body.include_vector_memory is not None:
        current["include_vector_memory"] = body.include_vector_memory
    if body.backup_dir is not None:
        current["backup_dir"] = body.backup_dir if body.backup_dir.strip() else None

    save_settings(current)

    # Sync the scheduler
    try:
        from shogun.services.backup_scheduler import sync_backup_schedule
        await sync_backup_schedule()
    except Exception as e:
        logger.warning("Could not sync backup schedule: %s", e)

    return current


@router.get("/list")
async def get_backups():
    """List all available backups."""
    backups = list_backups()
    settings = load_settings()
    return {
        "backups": backups,
        "total": len(backups),
        "max_backups": settings.get("max_backups", 5),
        "backup_dir": settings.get("backup_dir") or "data/backups/",
    }


@router.post("/create")
async def trigger_backup(body: CreateBackupRequest = CreateBackupRequest()):
    """Manually create a backup now."""
    result = create_backup(label=body.label)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Backup failed"))
    try:
        from shogun.services.event_logger import EventLogger
        await EventLogger.emit_system_event(
            "system.backup_created", f"Backup created: {result.get('filename', 'unknown')}",
            detail={"filename": result.get("filename"), "label": body.label},
        )
    except Exception:
        pass
    return result


@router.post("/complete")
async def trigger_complete_backup(
    body: CreateCompleteBackupRequest = CreateCompleteBackupRequest(),
    _actor: str = Depends(require_infrastructure_admin),
):
    """Archive every configured Shogun storage root for machine migration."""
    from shogun.services.complete_backup_service import create_complete_backup

    result = await run_in_threadpool(
        create_complete_backup,
        save_path=body.save_path,
        label=body.label,
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Complete backup failed"))
    return result


@router.post("/total-restore", status_code=202)
async def stage_complete_restore(
    file: UploadFile = File(...),
    restart_now: bool = Form(default=True),
    _actor: str = Depends(require_infrastructure_admin),
):
    """Validate and stage a complete backup for an offline startup restore."""
    from shogun.services.complete_backup_service import stage_total_restore

    try:
        result = await run_in_threadpool(
            stage_total_restore,
            file.file,
            filename=file.filename or "backup.zip",
        )
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if restart_now:
        from shogun.services.restart_service import request_restart

        try:
            result["restart"] = request_restart(delay_seconds=2.0)
        except RuntimeError as exc:
            result["restart"] = {"accepted": False, "message": str(exc)}
    return result


@router.get("/total-restore/status")
async def total_restore_status(_actor: str = Depends(require_infrastructure_admin)):
    from shogun.services.complete_backup_service import pending_total_restore

    return pending_total_restore()


@router.delete("/{filename}")
async def remove_backup(filename: str):
    """Delete a specific backup."""
    if not filename.startswith("shogun_backup_"):
        raise HTTPException(status_code=400, detail="Invalid backup filename")
    success = delete_backup(filename)
    if not success:
        raise HTTPException(status_code=404, detail="Backup not found")
    return {"deleted": filename}


@router.post("/restore/{filename}")
async def restore_from_backup(filename: str):
    """Restore Shogun from a backup. Requires restart afterwards."""
    if not filename.startswith("shogun_backup_"):
        raise HTTPException(status_code=400, detail="Invalid backup filename")
    result = restore_backup(filename)
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Restore failed"))
    try:
        from shogun.services.event_logger import EventLogger
        await EventLogger.emit_system_event(
            "system.backup_restored", f"System restored from backup: {filename}",
            severity="warn",
            detail={"filename": filename},
        )
    except Exception:
        pass
    return result
