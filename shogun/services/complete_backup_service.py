"""Configuration-driven complete backups and staged total restores.

Unlike the lightweight scheduled backup, this format discovers every configured
filesystem storage root and archives every file beneath those roots.  Restores
are staged while Shogun is running and applied before the next server startup,
when SQLite and embedded Qdrant are not open.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import zipfile
from collections.abc import Iterable
from contextlib import closing, nullcontext
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO
from uuid import uuid4

from sqlalchemy.engine import make_url

logger = logging.getLogger("shogun.complete_backups")

FORMAT_NAME = "shogun-complete-backup"
FORMAT_VERSION = 1
MANIFEST_NAME = "complete-manifest.json"
PAYLOAD_PREFIX = "payload"
PENDING_MARKER_NAME = "total-restore-pending.json"
MAX_ARCHIVE_FILES = 500_000
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class StorageRoot:
    root_id: str
    setting_key: str
    path: Path
    kind: str = "directory"
    selected_files: tuple[Path, ...] = ()


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def _state_dir(project_root: Path | None = None) -> Path:
    return (project_root or _project_root()) / ".states"


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", value).strip("-_")[:80] or "storage"


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _sqlite_path(database_url: str) -> Path | None:
    try:
        url = make_url(database_url)
    except Exception:
        return None
    if not url.get_backend_name().startswith("sqlite") or not url.database or url.database == ":memory:":
        return None
    return Path(url.database).expanduser().resolve()


def discover_storage_roots(
    *,
    settings_object: Any | None = None,
    project_root: Path | None = None,
) -> list[StorageRoot]:
    """Discover persistent roots from Settings instead of maintaining a file list."""
    if settings_object is None:
        from shogun.config import settings as settings_object

    root = (project_root or _project_root()).resolve()
    candidates: list[StorageRoot] = []
    field_names = getattr(type(settings_object), "model_fields", {})
    for field_name in field_names:
        value = getattr(settings_object, field_name, None)
        if not isinstance(value, Path):
            continue
        path = value.expanduser().resolve()
        if path.exists():
            candidates.append(StorageRoot(_safe_id(field_name), field_name, path))

    database_path = _sqlite_path(str(getattr(settings_object, "database_url", "")))
    if database_path and database_path.exists():
        candidates.append(StorageRoot("database-url", "database_url", database_path, kind="file"))

    # Prefer the broadest configured root.  Thus a future directory added below
    # DATA_PATH is included automatically without another backup code change.
    candidates.sort(key=lambda item: (len(item.path.parts), item.setting_key))
    selected: list[StorageRoot] = []
    for candidate in candidates:
        if any(candidate.path == item.path or _path_is_within(candidate.path, item.path) for item in selected):
            continue
        selected.append(candidate)

    environment_files = tuple(sorted(
        path
        for path in root.glob(".env*")
        if path.is_file()
        and not path.is_symlink()
        and not path.name.casefold().endswith(".example")
    ))
    if environment_files:
        selected.append(
            StorageRoot(
                "project-environment",
                "__project_environment__",
                root,
                kind="selected_files",
                selected_files=environment_files,
            )
        )
    return selected


def _iter_root_files(storage_root: StorageRoot, excluded_root: Path | None) -> Iterable[tuple[Path, Path]]:
    if storage_root.kind == "file":
        yield storage_root.path, Path(storage_root.path.name)
        return
    if storage_root.kind == "selected_files":
        for path in storage_root.selected_files:
            yield path, Path(path.name)
        return

    for current, directory_names, file_names in os.walk(storage_root.path, followlinks=False):
        current_path = Path(current)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if not (current_path / name).is_symlink()
            and not (excluded_root and _path_is_within((current_path / name).resolve(), excluded_root))
        )
        for name in sorted(file_names):
            path = current_path / name
            if path.is_symlink():
                continue
            resolved = path.resolve()
            if excluded_root and _path_is_within(resolved, excluded_root):
                continue
            # SQLite snapshots include committed WAL contents; stale sidecars
            # must not be restored alongside the clean snapshot.
            if name.endswith(("-wal", "-shm")):
                base = path.with_name(name.rsplit("-", 1)[0])
                if base.is_file() and _is_sqlite_database(base):
                    continue
            yield path, path.relative_to(storage_root.path)


def _is_sqlite_database(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 16:
        return False
    try:
        with path.open("rb") as handle:
            return handle.read(16) == b"SQLite format 3\x00"
    except OSError:
        return False


def _snapshot_sqlite(source: Path, temporary_directory: Path) -> Path:
    destination = temporary_directory / f"{uuid4().hex}.db"
    with closing(sqlite3.connect(str(source))) as source_db:
        with closing(sqlite3.connect(str(destination))) as snapshot_db:
            source_db.backup(snapshot_db)
    return destination


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_label(label: str | None) -> str:
    if not label:
        return ""
    normalized = re.sub(r"[^A-Za-z0-9_-]+", "-", label.strip()).strip("-_")[:64]
    return f"_{normalized}" if normalized else ""


def create_complete_backup(
    *,
    save_path: str | Path | None = None,
    label: str | None = None,
    settings_object: Any | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Create a checksummed archive of every file in every configured storage root."""
    root = (project_root or _project_root()).resolve()
    is_live_installation = settings_object is None and root == _project_root().resolve()
    if settings_object is None:
        from shogun.config import settings as settings_object
    database_url = str(getattr(settings_object, "database_url", ""))
    if database_url and not make_url(database_url).get_backend_name().startswith("sqlite"):
        return {
            "success": False,
            "error": "Complete Backup currently requires SQLite. Back up the configured external database separately.",
        }
    if getattr(settings_object, "qdrant_url", None):
        return {
            "success": False,
            "error": (
                "Complete Backup currently requires embedded Qdrant. "
                "Back up the configured Qdrant server separately."
            ),
        }
    destination_directory = Path(save_path or (root / "complete_backups")).expanduser()
    if not destination_directory.is_absolute():
        destination_directory = root / destination_directory
    destination_directory = destination_directory.resolve()
    destination_directory.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"shogun_complete_{timestamp}{_safe_label(label)}.zip"
    destination = destination_directory / filename
    if destination.exists():
        filename = f"{destination.stem}_{uuid4().hex[:8]}.zip"
        destination = destination_directory / filename
    storage_roots = discover_storage_roots(settings_object=settings_object, project_root=root)
    excluded_root = destination_directory if any(
        candidate.path == destination_directory or _path_is_within(destination_directory, candidate.path)
        for candidate in storage_roots
    ) else None

    manifest: dict[str, Any] = {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_project_root": str(root),
        "contains_secrets": True,
        "roots": [],
        "files": [],
    }
    archive_descriptor, archive_name = tempfile.mkstemp(prefix="shogun-complete-", suffix=".zip")
    os.close(archive_descriptor)
    temporary_archive = Path(archive_name)
    snapshot_directory = Path(tempfile.mkdtemp(prefix="shogun-sqlite-snapshots-"))
    try:
        if is_live_installation:
            from shogun.engine.vector_store import suspend_embedded_vector_store

            storage_guard = suspend_embedded_vector_store()
        else:
            storage_guard = nullcontext()
        with storage_guard, zipfile.ZipFile(
            temporary_archive,
            "w",
            compression=zipfile.ZIP_DEFLATED,
            allowZip64=True,
        ) as archive:
            for storage_root in storage_roots:
                root_files = 0
                root_bytes = 0
                for source, relative in _iter_root_files(storage_root, excluded_root):
                    snapshot = _snapshot_sqlite(source, snapshot_directory) if _is_sqlite_database(source) else source
                    relative_posix = PurePosixPath(*relative.parts).as_posix()
                    archive_name = f"{PAYLOAD_PREFIX}/{storage_root.root_id}/{relative_posix}"
                    size = snapshot.stat().st_size
                    checksum = _sha256_file(snapshot)
                    archive.write(snapshot, archive_name)
                    manifest["files"].append({
                        "root_id": storage_root.root_id,
                        "path": relative_posix,
                        "size": size,
                        "sha256": checksum,
                    })
                    root_files += 1
                    root_bytes += size
                manifest["roots"].append({
                    "id": storage_root.root_id,
                    "setting_key": storage_root.setting_key,
                    "kind": storage_root.kind,
                    "source_path": str(storage_root.path),
                    "files": root_files,
                    "bytes": root_bytes,
                })
            manifest["total_files"] = len(manifest["files"])
            manifest["total_bytes"] = sum(item["size"] for item in manifest["files"])
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2))
        os.replace(temporary_archive, destination)
        return {
            "success": True,
            "filename": filename,
            "path": str(destination),
            "files_count": manifest["total_files"],
            "original_size": manifest["total_bytes"],
            "compressed_size": destination.stat().st_size,
            "roots": manifest["roots"],
            "contains_secrets": True,
        }
    except Exception:
        logger.exception("Complete backup failed")
        return {"success": False, "error": "Complete backup failed. Check the Shogun logs for details."}
    finally:
        temporary_archive.unlink(missing_ok=True)
        shutil.rmtree(snapshot_directory, ignore_errors=True)


def _safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts or any(":" in part for part in path.parts):
        raise ValueError("Backup contains an unsafe path")
    return path


def _load_valid_manifest(archive: zipfile.ZipFile, *, verify_hashes: bool = True) -> dict[str, Any]:
    members = archive.infolist()
    if len(members) > MAX_ARCHIVE_FILES:
        raise ValueError("Complete backup contains too many files")
    if sum(member.file_size for member in members) > MAX_ARCHIVE_BYTES:
        raise ValueError("Expanded complete backup exceeds the 100 GiB safety limit")
    for member in members:
        _safe_member_path(member.filename)
        if member.is_dir() or ((member.external_attr >> 16) & 0o170000) == 0o120000:
            if not member.is_dir():
                raise ValueError("Complete backup contains a symbolic link")
    member_names = [member.filename for member in members if not member.is_dir()]
    if len(member_names) != len(set(member_names)):
        raise ValueError("Complete backup contains duplicate members")
    try:
        manifest = json.loads(archive.read(MANIFEST_NAME))
    except (KeyError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("Missing or invalid complete backup manifest") from exc
    if manifest.get("format") != FORMAT_NAME or manifest.get("format_version") != FORMAT_VERSION:
        raise ValueError("This is not a supported Shogun complete backup")

    roots = manifest.get("roots")
    files = manifest.get("files")
    if not isinstance(roots, list) or not isinstance(files, list):
        raise ValueError("Complete backup manifest is incomplete")
    if any(not isinstance(item, dict) for item in roots):
        raise ValueError("Complete backup contains an invalid storage root")
    root_ids: set[str] = set()
    for root_record in roots:
        root_id = str(root_record.get("id", ""))
        setting_key = str(root_record.get("setting_key", ""))
        kind = str(root_record.get("kind", ""))
        if not root_id or _safe_id(root_id) != root_id or root_id in root_ids:
            raise ValueError("Complete backup contains an invalid storage root ID")
        if kind not in {"directory", "file", "selected_files"}:
            raise ValueError("Complete backup contains an invalid storage root kind")
        if kind == "selected_files" and (
            root_id != "project-environment" or setting_key != "__project_environment__"
        ):
            raise ValueError("Complete backup contains an invalid selected-file root")
        if kind == "file" and setting_key != "database_url":
            raise ValueError("Complete backup contains an invalid file storage root")
        if kind == "directory" and (not setting_key or setting_key.startswith("__")):
            raise ValueError("Complete backup contains an invalid directory storage root")
        root_ids.add(root_id)
    archive_names = set(archive.namelist())
    if len(files) > MAX_ARCHIVE_FILES:
        raise ValueError("Complete backup manifest contains too many files")
    expected_payload_names: set[str] = set()
    root_kinds = {str(item["id"]): str(item["kind"]) for item in roots}
    for item in files:
        if not isinstance(item, dict) or item.get("root_id") not in root_ids:
            raise ValueError("Complete backup manifest references an unknown storage root")
        relative = _safe_member_path(str(item.get("path", "")))
        root_id = str(item["root_id"])
        if root_kinds[root_id] == "selected_files" and (
            len(relative.parts) != 1
            or not relative.name.startswith(".env")
            or relative.name.casefold().endswith(".example")
        ):
            raise ValueError("Complete backup contains an invalid environment file")
        if root_kinds[root_id] == "file" and len(relative.parts) != 1:
            raise ValueError("Complete backup contains an invalid file-root path")
        member_name = f"{PAYLOAD_PREFIX}/{item['root_id']}/{relative.as_posix()}"
        if member_name in expected_payload_names:
            raise ValueError("Complete backup manifest contains a duplicate file")
        expected_payload_names.add(member_name)
        if member_name not in archive_names:
            raise ValueError(f"Complete backup is missing {relative.as_posix()}")
        member = archive.getinfo(member_name)
        if member.file_size != item.get("size"):
            raise ValueError(f"Size verification failed for {relative.as_posix()}")
        if verify_hashes:
            digest = hashlib.sha256()
            with archive.open(member_name) as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            if digest.hexdigest() != item.get("sha256"):
                raise ValueError(f"Checksum verification failed for {relative.as_posix()}")
    unexpected = {
        name for name in archive_names
        if name != MANIFEST_NAME and not name.endswith("/") and name not in expected_payload_names
    }
    if unexpected:
        raise ValueError("Complete backup contains files that are not declared in its manifest")
    return manifest


def stage_total_restore(
    source: BinaryIO,
    *,
    filename: str,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Stream, validate, and stage a complete backup for the next restart."""
    root = (project_root or _project_root()).resolve()
    if not filename.lower().endswith(".zip"):
        raise ValueError("Total Restore requires a Shogun complete-backup ZIP")
    state_directory = _state_dir(root)
    state_directory.mkdir(parents=True, exist_ok=True)
    staged_path = state_directory / f"total-restore-{uuid4().hex}.zip"
    total = 0
    try:
        with staged_path.open("wb") as destination:
            while chunk := source.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError("Complete backup archive exceeds the 100 GiB safety limit")
                destination.write(chunk)
        with zipfile.ZipFile(staged_path) as archive:
            manifest = _load_valid_manifest(archive, verify_hashes=True)
        marker = state_directory / PENDING_MARKER_NAME
        previous_archive: Path | None = None
        if marker.is_file():
            try:
                previous = json.loads(marker.read_text(encoding="utf-8"))
                previous_archive = state_directory / Path(str(previous.get("archive", ""))).name
            except (OSError, json.JSONDecodeError):
                previous_archive = None
        temporary_marker = marker.with_suffix(".tmp")
        temporary_marker.write_text(json.dumps({
            "archive": staged_path.name,
            "staged_at": datetime.now(timezone.utc).isoformat(),
            "source_filename": Path(filename).name,
        }, indent=2), encoding="utf-8")
        os.replace(temporary_marker, marker)
        if previous_archive and previous_archive != staged_path:
            previous_archive.unlink(missing_ok=True)
        return {
            "success": True,
            "staged": True,
            "files_count": manifest.get("total_files", len(manifest.get("files", []))),
            "original_size": manifest.get("total_bytes", 0),
            "created_at": manifest.get("created_at"),
            "restart_required": True,
            "message": "Total Restore is validated and staged. Restart Shogun to apply it before startup.",
        }
    except Exception:
        staged_path.unlink(missing_ok=True)
        raise


def _destination_for_root(root_record: dict[str, Any], settings_object: Any, project_root: Path) -> Path:
    setting_key = str(root_record.get("setting_key", ""))
    kind = str(root_record.get("kind", "directory"))
    if setting_key == "__project_environment__" and kind == "selected_files":
        return project_root
    if setting_key == "database_url":
        path = _sqlite_path(str(getattr(settings_object, "database_url", "")))
        if path is None:
            raise ValueError("The target Shogun does not use a restorable SQLite database")
        return path
    value = getattr(settings_object, setting_key, None)
    if not isinstance(value, Path):
        raise ValueError(f"Target Shogun has no storage setting named {setting_key}")
    return value.expanduser().resolve()


def _relocate_text_file(path: Path, source_root: str, destination_root: str) -> None:
    if not source_root or source_root == destination_root:
        return
    if path.name.startswith(".env") or path.suffix.casefold() in {".json", ".yaml", ".yml", ".toml", ".ini"}:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return
        relocated = text.replace(source_root, destination_root).replace(
            source_root.replace("\\", "/"), destination_root.replace("\\", "/")
        )
        relocated = relocated.replace(
            source_root.replace("\\", "\\\\"),
            destination_root.replace("\\", "\\\\"),
        )
        if relocated != text:
            path.write_text(relocated, encoding="utf-8")


def _remove_path(path: Path) -> None:
    if path.is_dir():
        def make_writable_and_retry(function, target, _error_info):
            os.chmod(target, stat.S_IWRITE)
            function(target)

        shutil.rmtree(path, onerror=make_writable_and_retry)
    else:
        if path.exists():
            path.chmod(stat.S_IWRITE)
        path.unlink(missing_ok=True)


def _preserve_for_rollback(source: Path, rollback: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, rollback)
    else:
        shutil.copy2(source, rollback)
    _remove_path(source)


def _restore_rollback(destination: Path, rollback: Path) -> None:
    if rollback.is_dir():
        shutil.copytree(rollback, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(rollback, destination)
    _remove_path(rollback)


def apply_pending_total_restore(
    *,
    project_root: Path | None = None,
    settings_object: Any | None = None,
) -> dict[str, Any]:
    """Apply a staged archive. Call before database/Qdrant startup."""
    root = (project_root or _project_root()).resolve()
    marker = _state_dir(root) / PENDING_MARKER_NAME
    if not marker.is_file():
        return {"applied": False}
    pending = json.loads(marker.read_text(encoding="utf-8"))
    archive_path = marker.parent / Path(str(pending.get("archive", ""))).name
    if not archive_path.is_file():
        raise RuntimeError("Pending Total Restore archive is missing")
    if settings_object is None:
        from shogun.config import settings as settings_object

    with zipfile.ZipFile(archive_path) as archive:
        manifest = _load_valid_manifest(archive, verify_hashes=True)
        root_records = {str(item["id"]): item for item in manifest["roots"]}
        destinations = {
            root_id: _destination_for_root(record, settings_object, root)
            for root_id, record in root_records.items()
        }
        directory_destinations = [
            destinations[root_id]
            for root_id, record in root_records.items()
            if record.get("kind") == "directory"
        ]
        for index, destination in enumerate(directory_destinations):
            for other in directory_destinations[index + 1:]:
                if _path_is_within(destination, other) or _path_is_within(other, destination):
                    raise RuntimeError("Target storage settings overlap and cannot be restored safely")
        for root_id, destination in destinations.items():
            record = root_records[root_id]
            if record.get("kind") == "directory" and destination == Path(destination.anchor):
                raise RuntimeError("Refusing to replace a filesystem root")
            if record.get("kind") == "directory" and destination == root:
                raise RuntimeError("Refusing to replace the Shogun application directory")

        # Preserve the destination state before the destructive swap.
        safety = create_complete_backup(
            save_path=root / "complete_backups",
            label="pre-total-restore",
            settings_object=settings_object,
            project_root=root,
        )
        if not safety.get("success"):
            raise RuntimeError("Could not create the automatic pre-restore safety backup")

        work_directory = Path(tempfile.mkdtemp(prefix="shogun-total-restore-"))
        rollback_paths: list[tuple[Path, Path]] = []
        swapped: list[Path] = []
        try:
            relocations = [
                (str(manifest.get("source_project_root", "")), str(root)),
                *[
                    (str(record.get("source_path", "")), str(destinations[root_id]))
                    for root_id, record in root_records.items()
                ],
            ]
            # Build every restored root fully before touching live state.
            staged_roots: dict[str, Path] = {}
            for root_id, record in root_records.items():
                if record.get("kind") in {"selected_files", "file"}:
                    continue
                staged = work_directory / root_id
                staged.mkdir(parents=True, exist_ok=True)
                staged_roots[root_id] = staged
            for item in manifest["files"]:
                root_id = str(item["root_id"])
                relative = _safe_member_path(str(item["path"]))
                record = root_records[root_id]
                if record.get("kind") == "selected_files":
                    staged = work_directory / "selected-files" / root_id / Path(*relative.parts)
                elif record.get("kind") == "file":
                    staged = work_directory / "file-roots" / root_id / Path(*relative.parts)
                else:
                    staged = staged_roots[root_id] / Path(*relative.parts)
                staged.parent.mkdir(parents=True, exist_ok=True)
                member_name = f"{PAYLOAD_PREFIX}/{root_id}/{relative.as_posix()}"
                with archive.open(member_name) as source, staged.open("wb") as destination:
                    shutil.copyfileobj(source, destination, length=1024 * 1024)
                for source_path, destination_path in relocations:
                    _relocate_text_file(staged, source_path, destination_path)

            # Directory/file roots are non-overlapping in each generated archive.
            for root_id, staged in staged_roots.items():
                destination = destinations[root_id]
                destination.parent.mkdir(parents=True, exist_ok=True)
                rollback = destination.with_name(f".{destination.name}.pre-total-restore-{uuid4().hex}")
                if destination.exists():
                    _preserve_for_rollback(destination, rollback)
                    rollback_paths.append((destination, rollback))
                os.replace(staged, destination)
                swapped.append(destination)

            for root_id, record in root_records.items():
                if record.get("kind") != "file":
                    continue
                candidates = [
                    item for item in manifest["files"] if item["root_id"] == root_id
                ]
                if len(candidates) != 1:
                    raise RuntimeError("A file storage root must contain exactly one file")
                relative = _safe_member_path(str(candidates[0]["path"]))
                staged = work_directory / "file-roots" / root_id / Path(*relative.parts)
                destination = destinations[root_id]
                destination.parent.mkdir(parents=True, exist_ok=True)
                rollback = destination.with_name(f".{destination.name}.pre-total-restore-{uuid4().hex}")
                if destination.exists():
                    _preserve_for_rollback(destination, rollback)
                    rollback_paths.append((destination, rollback))
                os.replace(staged, destination)
                swapped.append(destination)

            # Environment files live in the application root and are swapped individually.
            for root_id, record in root_records.items():
                if record.get("kind") != "selected_files":
                    continue
                selected_root = work_directory / "selected-files" / root_id
                archived_names = {str(item["path"]) for item in manifest["files"] if item["root_id"] == root_id}
                for current in root.glob(".env*"):
                    if current.is_file() and current.name not in archived_names:
                        current.unlink()
                for relative_name in archived_names:
                    relative = _safe_member_path(relative_name)
                    source = selected_root / Path(*relative.parts)
                    destination = root / Path(*relative.parts)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, destination)

            for _destination, rollback in rollback_paths:
                _remove_path(rollback)
            marker.unlink(missing_ok=True)
            # Windows does not permit deleting the staged ZIP while ZipFile
            # still owns its file handle. The surrounding context may close it
            # again safely after this early close.
            archive.close()
            archive_path.unlink(missing_ok=True)
            return {
                "applied": True,
                "files_restored": len(manifest["files"]),
                "safety_backup": safety.get("path"),
            }
        except Exception:
            logger.exception("Total Restore failed; rolling back swapped storage roots")
            for destination in reversed(swapped):
                _remove_path(destination)
            for destination, rollback in reversed(rollback_paths):
                if rollback.exists():
                    _restore_rollback(destination, rollback)
            raise
        finally:
            shutil.rmtree(work_directory, ignore_errors=True)


def pending_total_restore(*, project_root: Path | None = None) -> dict[str, Any]:
    marker = _state_dir(project_root) / PENDING_MARKER_NAME
    if not marker.is_file():
        return {"pending": False}
    try:
        return {"pending": True, **json.loads(marker.read_text(encoding="utf-8"))}
    except (OSError, json.JSONDecodeError):
        return {"pending": True, "invalid_marker": True}
