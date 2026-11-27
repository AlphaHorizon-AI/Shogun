"""Workspace API — Local folder setup and workspace file operations for AgentFlow."""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from shogun.config import settings

log = logging.getLogger("shogun.api.workspace")
router = APIRouter(prefix="/workspace", tags=["Workspace"])


def _get_workspace_root() -> Path:
    root = settings.workspace_path.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _validate_path(root: Path, relative: str) -> Path:
    if not relative or relative.strip() == "":
        return root

    rel = relative.strip()
    if ".." in rel:
        raise HTTPException(400, f"Path traversal blocked: '{rel}'")
    if rel.startswith("/") or rel.startswith("\\") or rel.startswith("\\\\"):
        raise HTTPException(400, f"Absolute or UNC paths are not allowed: '{rel}'")

    target = (root / rel).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise HTTPException(400, f"Path escapes workspace boundary: '{rel}'")
    return target


def _build_tree(path: Path, root: Path, max_depth: int = 8, depth: int = 0) -> list[dict[str, Any]]:
    if depth > max_depth:
        return []
    entries: list[dict[str, Any]] = []
    try:
        items = sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except PermissionError:
        return []

    for item in items:
        rel = str(item.relative_to(root)).replace("\\", "/")
        entry: dict[str, Any] = {
            "name": item.name,
            "path": rel,
            "type": "directory" if item.is_dir() else "file",
        }
        try:
            item_stat = item.stat()
            entry["created_at"] = datetime.fromtimestamp(item_stat.st_ctime).astimezone().isoformat()
            entry["modified_at"] = datetime.fromtimestamp(item_stat.st_mtime).astimezone().isoformat()
        except OSError:
            item_stat = None
        if item.is_file():
            entry["size"] = item_stat.st_size if item_stat else 0
            entry["extension"] = item.suffix.lstrip(".")
        elif item.is_dir():
            entry["children"] = _build_tree(item, root, max_depth, depth + 1)
        entries.append(entry)
    return entries


class WorkspaceConfigUpdate(BaseModel):
    workspace_path: str = Field(..., min_length=1, max_length=2000)


class WriteRequest(BaseModel):
    path: str
    content: str


class MkdirRequest(BaseModel):
    path: str


class RenameRequest(BaseModel):
    old_path: str
    new_path: str


@router.get("/config")
async def get_workspace_config():
    """Return the configured local folder path used by AgentFlow."""
    root = _get_workspace_root()
    return {
        "success": True,
        "data": {
            "workspace_path": str(root),
            "exists": root.is_dir(),
            "input_dir": str(root / "input"),
            "output_dir": str(root / "output"),
        },
    }


@router.put("/config")
async def update_workspace_config(req: WorkspaceConfigUpdate):
    """Set and persist the local folder path used by AgentFlow."""
    import tempfile

    raw = req.workspace_path.strip()
    if not raw:
        raise HTTPException(400, "workspace_path cannot be empty")
    expanded = os.path.expandvars(os.path.expanduser(raw))
    if not os.path.isabs(expanded):
        raise HTTPException(400, "Please provide an absolute local folder path")
    normalized = os.path.normpath(os.path.abspath(expanded))
    allowed_roots = (
        os.path.realpath(str(Path.home())),
        os.path.realpath(str(Path(__file__).resolve().parent.parent.parent.parent)),
        os.path.realpath(tempfile.gettempdir()),
    )
    for root in allowed_roots:
        if normalized == root:
            resolved = settings.save_persisted_workspace(Path(root))
            return {
                "success": True,
                "data": {
                    "workspace_path": str(resolved),
                    "exists": True,
                    "input_dir": str(resolved / "input"),
                    "output_dir": str(resolved / "output"),
                },
            }
        if normalized.startswith(root + os.sep):
            rel = normalized[len(root) + len(os.sep) :]
            candidate = os.path.normpath(os.path.join(root, rel))
            if candidate.startswith(root + os.sep):
                if os.path.exists(candidate) and not os.path.isdir(candidate):
                    raise HTTPException(400, f"Path exists and is not a folder: {candidate}")
                try:
                    resolved = settings.save_persisted_workspace(Path(candidate))
                except OSError as exc:
                    raise HTTPException(400, f"Could not access or create folder: {exc}") from exc
                log.info("Updated local workspace folder to: %s", resolved)
                return {
                    "success": True,
                    "data": {
                        "workspace_path": str(resolved),
                        "exists": True,
                        "input_dir": str(resolved / "input"),
                        "output_dir": str(resolved / "output"),
                    },
                }

    raise HTTPException(
        400,
        "Workspace folder must be located inside your user home, project directory, or temp folder",
    )


@router.get("/info")
async def workspace_info():
    """Get local workspace folder metadata."""
    root = _get_workspace_root()
    total_files = sum(1 for f in root.rglob("*") if f.is_file())
    total_dirs = sum(1 for f in root.rglob("*") if f.is_dir())
    total_size = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())

    return {
        "success": True,
        "data": {
            "path": str(root),
            "enabled": True,
            "total_files": total_files,
            "total_directories": total_dirs,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        },
    }


@router.get("/tree")
async def workspace_tree():
    """Return the directory tree of the configured local workspace folder."""
    root = _get_workspace_root()
    tree = _build_tree(root, root)
    return {"success": True, "data": {"root": str(root), "tree": tree}}


@router.get("/read")
async def read_file(path: str):
    root = _get_workspace_root()
    target = _validate_path(root, path)
    if not target.exists():
        raise HTTPException(404, f"File not found: {path}")
    if not target.is_file():
        raise HTTPException(400, f"Not a file: {path}")
    size = target.stat().st_size
    if size > 10 * 1024 * 1024:
        raise HTTPException(413, f"File too large to read in browser: {size} bytes")
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(415, f"Cannot read as text (binary file): {path}")
    return {
        "success": True,
        "data": {"path": path, "content": content, "size": size, "extension": target.suffix.lstrip(".")},
    }


@router.post("/write")
async def write_file(req: WriteRequest):
    root = _get_workspace_root()
    target = _validate_path(root, req.path)
    target.parent.mkdir(parents=True, exist_ok=True)
    existed = target.exists()
    target.write_text(req.content, encoding="utf-8")
    return {
        "success": True,
        "data": {"path": req.path, "action": "overwritten" if existed else "created", "size": target.stat().st_size},
    }


@router.post("/mkdir")
async def make_directory(req: MkdirRequest):
    root = _get_workspace_root()
    target = _validate_path(root, req.path)
    existed = target.exists()
    target.mkdir(parents=True, exist_ok=True)
    return {
        "success": True,
        "data": {"path": req.path, "action": "already_exists" if existed else "created"},
    }


@router.delete("/delete")
async def delete_item(path: str):
    root = _get_workspace_root()
    target = _validate_path(root, path)
    if not target.exists():
        raise HTTPException(404, f"Not found: {path}")
    if target == root:
        raise HTTPException(400, "Cannot delete the workspace root")
    if target.is_file():
        target.unlink()
    else:
        try:
            target.rmdir()
        except OSError as exc:
            raise HTTPException(400, f"Directory is not empty: {path}") from exc
    return {"success": True, "data": {"deleted": path}}


@router.post("/rename")
async def rename_item(req: RenameRequest):
    root = _get_workspace_root()
    src = _validate_path(root, req.old_path)
    dst = _validate_path(root, req.new_path)
    if not src.exists():
        raise HTTPException(404, f"Source not found: {req.old_path}")
    if dst.exists():
        raise HTTPException(409, f"Destination already exists: {req.new_path}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"success": True, "data": {"old_path": req.old_path, "new_path": req.new_path}}


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), directory: str = Form("")):
    root = _get_workspace_root()
    dest_dir = _validate_path(root, directory) if directory else root
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.bin").name
    target = _validate_path(root, str((dest_dir / safe_name).relative_to(root)))
    content = await file.read()
    target.write_bytes(content)
    rel = str(target.relative_to(root)).replace("\\", "/")
    return {"success": True, "data": {"path": rel, "size": len(content)}}


@router.get("/download")
async def download_file(path: str):
    root = _get_workspace_root()
    target = _validate_path(root, path)
    if not target.is_file():
        raise HTTPException(404, f"File not found: {path}")
    return FileResponse(str(target), filename=target.name)
