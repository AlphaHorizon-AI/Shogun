"""
Shogun Backups API — Create, list, restore, and configure automatic backups.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shogun.services.backup_service import (
    create_backup,
    list_backups,
    delete_backup,
    restore_backup,
    load_settings,
    save_settings,
)

logger = logging.getLogger("shogun.api.backups")
router = APIRouter(prefix="/backups", tags=["backups"])


# ── Models ───────────────────────────────────────────────────────

class BackupSettingsUpdate(BaseModel):
    enabled: Optional[bool] = None
    interval_hours: Optional[int] = None
    max_backups: Optional[int] = None
    include_vector_memory: Optional[bool] = None
    backup_dir: Optional[str] = None


class CreateBackupRequest(BaseModel):
    label: Optional[str] = None


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
    return result


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
    return result
