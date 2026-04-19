"""
Shogun Backup Service — Scheduled backups with configurable retention.

Backs up:
  - Database (shogun.db)
  - Configuration files (configs/)
  - Constitution & Mandate
  - version.json

Does NOT back up:
  - Vector memory (qdrant/) — too large, can be rebuilt
  - Frontend build artifacts
  - Virtual environments
"""

import json
import logging
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger("shogun.backups")

# ── Configuration file ───────────────────────────────────────────
# Stored in configs/backup_settings.json

DEFAULT_SETTINGS = {
    "enabled": False,
    "interval_hours": 24,
    "max_backups": 5,
    "include_vector_memory": False,
    "last_backup": None,
    "backup_dir": None,  # None = use default (data/backups/)
}


def _get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _get_settings_path() -> Path:
    root = _get_project_root()
    return root / "configs" / "backup_settings.json"


def _get_backup_dir() -> Path:
    settings = load_settings()
    if settings.get("backup_dir"):
        d = Path(settings["backup_dir"])
    else:
        d = _get_project_root() / "data" / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_settings() -> dict:
    """Load backup settings from disk."""
    path = _get_settings_path()
    if not path.exists():
        return dict(DEFAULT_SETTINGS)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Merge with defaults for any missing keys
        merged = dict(DEFAULT_SETTINGS)
        merged.update(data)
        return merged
    except Exception as e:
        logger.error("Failed to load backup settings: %s", e)
        return dict(DEFAULT_SETTINGS)


def save_settings(settings: dict) -> None:
    """Persist backup settings to disk."""
    path = _get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def create_backup(label: Optional[str] = None) -> dict:
    """
    Create a backup ZIP of the Shogun installation.

    Returns metadata about the created backup.
    """
    root = _get_project_root()
    backup_dir = _get_backup_dir()
    settings = load_settings()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label_suffix = f"_{label}" if label else ""
    filename = f"shogun_backup_{timestamp}{label_suffix}.zip"
    backup_path = backup_dir / filename

    # Items to back up
    items_to_backup = []
    files_count = 0
    total_size = 0

    # 1. Database
    db_file = root / "data" / "shogun.db"
    if db_file.exists():
        items_to_backup.append(("shogun.db", db_file))

    # 2. Configs directory
    configs_dir = root / "configs"
    if configs_dir.exists():
        for f in configs_dir.rglob("*"):
            if f.is_file():
                rel = f.relative_to(root)
                items_to_backup.append((str(rel), f))

    # 3. Constitution & Mandate (may be in data/governance/)
    governance_dir = root / "data" / "governance"
    if governance_dir.exists():
        for f in governance_dir.rglob("*"):
            if f.is_file():
                rel = f.relative_to(root)
                items_to_backup.append((str(rel), f))

    # 4. version.json
    version_file = root / "version.json"
    if version_file.exists():
        items_to_backup.append(("version.json", version_file))

    # 5. .env file
    env_file = root / ".env"
    if env_file.exists():
        items_to_backup.append((".env", env_file))

    # 6. Setup state
    setup_file = root / "configs" / "setup.json"
    if setup_file.exists() and not any(name == "configs/setup.json" for name, _ in items_to_backup):
        items_to_backup.append(("configs/setup.json", setup_file))

    # 7. Optionally include vector memory
    if settings.get("include_vector_memory", False):
        qdrant_dir = root / "data" / "qdrant"
        if qdrant_dir.exists():
            for f in qdrant_dir.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(root)
                    items_to_backup.append((str(rel), f))

    # Create ZIP
    try:
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for arc_name, file_path in items_to_backup:
                zf.write(file_path, arc_name)
                files_count += 1
                total_size += file_path.stat().st_size

        backup_size = backup_path.stat().st_size

        # Update last_backup timestamp
        settings["last_backup"] = datetime.now(timezone.utc).isoformat()
        save_settings(settings)

        logger.info("Backup created: %s (%d files, %s)", filename, files_count, _format_size(backup_size))

        # Enforce retention
        _enforce_retention(settings.get("max_backups", 5))

        return {
            "success": True,
            "filename": filename,
            "path": str(backup_path),
            "files_count": files_count,
            "original_size": total_size,
            "compressed_size": backup_size,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error("Backup failed: %s", e, exc_info=True)
        return {
            "success": False,
            "error": str(e),
        }


def _enforce_retention(max_backups: int) -> int:
    """Delete old backups beyond the retention limit. Returns number deleted."""
    backup_dir = _get_backup_dir()
    backups = sorted(
        [f for f in backup_dir.glob("shogun_backup_*.zip")],
        key=lambda f: f.stat().st_mtime,
        reverse=True,  # newest first
    )

    deleted = 0
    if len(backups) > max_backups:
        for old in backups[max_backups:]:
            try:
                old.unlink()
                deleted += 1
                logger.info("Deleted old backup: %s", old.name)
            except Exception as e:
                logger.warning("Could not delete old backup %s: %s", old.name, e)

    return deleted


def list_backups() -> list[dict]:
    """List all available backups."""
    backup_dir = _get_backup_dir()
    backups = sorted(
        [f for f in backup_dir.glob("shogun_backup_*.zip")],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    result = []
    for f in backups:
        stat = f.stat()
        result.append({
            "filename": f.name,
            "size": stat.st_size,
            "size_formatted": _format_size(stat.st_size),
            "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        })

    return result


def delete_backup(filename: str) -> bool:
    """Delete a specific backup file."""
    backup_dir = _get_backup_dir()
    path = backup_dir / filename
    if not path.exists() or not filename.startswith("shogun_backup_"):
        return False
    try:
        path.unlink()
        return True
    except Exception:
        return False


def restore_backup(filename: str) -> dict:
    """
    Restore from a backup ZIP.

    CAUTION: This overwrites current config and database files.
    """
    backup_dir = _get_backup_dir()
    path = backup_dir / filename

    if not path.exists():
        return {"success": False, "error": f"Backup not found: {filename}"}

    root = _get_project_root()
    restored = 0

    try:
        with zipfile.ZipFile(path, "r") as zf:
            for member in zf.namelist():
                dest = root / member
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                    restored += 1

        logger.info("Restored backup %s (%d files)", filename, restored)
        return {
            "success": True,
            "filename": filename,
            "files_restored": restored,
            "message": "Backup restored. Please restart Shogun for changes to take effect.",
            "restart_required": True,
        }

    except Exception as e:
        logger.error("Restore failed: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
