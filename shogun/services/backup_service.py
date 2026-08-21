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
import re
import shutil
import sqlite3
import zipfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from shogun.services.release_metadata import get_release_metadata

logger = logging.getLogger("shogun.backups")

_BACKUP_NAME = re.compile(
    r"^shogun_backup_\d{8}_\d{6}(?:_[A-Za-z0-9_-]{1,64})?\.zip$"
)
_MAX_RESTORE_FILES = 20_000
_MAX_RESTORE_BYTES = 10 * 1024 * 1024 * 1024

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


def _safe_label(label: str | None) -> str:
    if not label:
        return ""
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", label.strip()).strip("-_")[:64]
    return f"_{normalized}" if normalized else ""


def _backup_path(filename: str, *, must_exist: bool = True) -> Path | None:
    """Resolve a generated backup name without allowing directory traversal."""
    if Path(filename).name != filename or not _BACKUP_NAME.fullmatch(filename):
        return None
    backup_dir = _get_backup_dir().resolve()
    candidate = (backup_dir / filename).resolve()
    if candidate.parent != backup_dir or (must_exist and not candidate.is_file()):
        return None
    return candidate


def _restore_destination(root: Path, member: zipfile.ZipInfo) -> Path | None:
    """Return a safe, supported restore destination for a ZIP member."""
    name = member.filename.replace("\\", "/")
    if member.is_dir() or name == "manifest.json":
        return None
    parts = Path(name).parts
    if not parts or Path(name).is_absolute() or ".." in parts or ":" in parts[0]:
        raise ValueError("Backup contains an unsafe path")
    # Reject Unix symlinks; extracting them could escape the project root.
    if (member.external_attr >> 16) & 0o170000 == 0o120000:
        raise ValueError("Backup contains a symbolic link")
    allowed = (
        name in {"shogun.db", "version.json", ".env"}
        or name.startswith("configs/")
        or name.startswith("data/governance/")
        or name.startswith("data/qdrant/")
    )
    if not allowed:
        raise ValueError("Backup contains an unsupported file")
    candidate = (root / Path(*parts)).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("Backup path escapes the installation directory")
    return candidate


def create_backup(label: str | None = None) -> dict:
    """
    Create a backup ZIP of the Shogun installation.

    Returns metadata about the created backup.
    """
    root = _get_project_root()
    backup_dir = _get_backup_dir()
    settings = load_settings()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    label_suffix = _safe_label(label)
    filename = f"shogun_backup_{timestamp}{label_suffix}.zip"
    backup_path = backup_dir / filename
    db_snapshot_path = backup_dir / f".{filename}.db-snapshot"

    # Items to back up
    items_to_backup = []
    files_count = 0
    total_size = 0

    # 1. Database
    db_file = root / "data" / "shogun.db"
    if db_file.exists():
        try:
            with closing(sqlite3.connect(str(db_file))) as source_db:
                with closing(sqlite3.connect(str(db_snapshot_path))) as snapshot_db:
                    source_db.backup(snapshot_db)
            items_to_backup.append(("shogun.db", db_snapshot_path))
        except Exception:
            db_snapshot_path.unlink(missing_ok=True)
            raise

    # 2. Configs directory
    configs_dir = root / "configs"
    if configs_dir.exists():
        for f in configs_dir.rglob("*"):
            if f.is_file():
                rel = f.relative_to(root)
                items_to_backup.append((rel.as_posix(), f))

    # 3. Constitution & Mandate (may be in data/governance/)
    governance_dir = root / "data" / "governance"
    if governance_dir.exists():
        for f in governance_dir.rglob("*"):
            if f.is_file():
                rel = f.relative_to(root)
                items_to_backup.append((rel.as_posix(), f))

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
                    items_to_backup.append((rel.as_posix(), f))

    # Create ZIP
    try:
        release = get_release_metadata()
        with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps({
                "shogun_version": release["version"],
                "shogun_build": release["build"],
                "shogun_release_id": release["release_id"],
                "shogun_git_sha": release["git_sha"],
                "shogun_distribution_status": release["distribution_status"],
                "shogun_working_tree_modified": release["working_tree_modified"],
                "shogun_release_date": release["release_date"],
                "backup_format": "1.0",
                "backup_type": "installation",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "includes_raw_db": db_file.exists(),
            }, indent=2))
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

    except Exception:
        logger.exception("Backup failed")
        return {
            "success": False,
            "error": "Backup creation failed. Check the Shogun logs for details.",
        }
    finally:
        db_snapshot_path.unlink(missing_ok=True)


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
    path = _backup_path(filename)
    if path is None:
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
    path = _backup_path(filename)
    if path is None:
        return {"success": False, "error": "Backup not found or filename is invalid."}

    root = _get_project_root()
    restored = 0

    try:
        root = root.resolve()
        with zipfile.ZipFile(path, "r") as zf:
            members = zf.infolist()
            if len(members) > _MAX_RESTORE_FILES:
                raise ValueError("Backup contains too many files")
            if sum(member.file_size for member in members) > _MAX_RESTORE_BYTES:
                raise ValueError("Backup is too large to restore safely")
            for member in members:
                dest = _restore_destination(root, member)
                if dest is None:
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, open(dest, "wb") as dst:
                    shutil.copyfileobj(src, dst, length=1024 * 1024)
                    restored += 1

        logger.info("Restored backup %s (%d files)", filename, restored)
        return {
            "success": True,
            "filename": filename,
            "files_restored": restored,
            "message": "Backup restored. Please restart Shogun for changes to take effect.",
            "restart_required": True,
        }

    except Exception:
        logger.exception("Restore failed")
        return {"success": False, "error": "Backup restore failed. Check the Shogun logs for details."}


def _format_size(size_bytes: int) -> str:
    """Human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
