"""OpenClaw Markdown import into native Shogun memory (Order 17)."""

from __future__ import annotations

import hashlib
import io
import json
import re
import uuid
import zipfile
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import yaml
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.agent import Agent
from shogun.db.models.memory_import import MemoryImportBatch, MemoryImportItem
from shogun.db.models.memory_record import MemoryRecord
from shogun.engine.vector_store import get_vector_store
from shogun.services.event_logger import EventLogger

FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)
FIELD_SYNONYMS = {
    "type": "memory_type",
    "category": "memory_type",
    "weight": "importance",
    "priority": "importance",
    "labels": "tags",
    "created": "created_at",
    "modified": "updated_at",
    "updated": "updated_at",
    "origin": "source",
    "project": "source_project",
}
TYPE_MAP = {
    "episodic": "episodic",
    "conversation": "episodic",
    "conversation_summary": "episodic",
    "summary": "episodic",
    "preference": "persona",
    "pref": "persona",
    "persona": "persona",
    "decision": "procedural",
    "instruction": "procedural",
    "procedure": "procedural",
    "procedural": "procedural",
    "skill": "skills",
    "skill_note": "skills",
    "skills": "skills",
    "fact": "semantic",
    "project": "semantic",
    "project_context": "semantic",
    "context": "semantic",
    "analysis": "semantic",
    "system_note": "semantic",
    "semantic": "semantic",
    "unknown": "semantic",
}
DECAY_MAP = {
    "normal": "medium",
    "medium": "medium",
    "slow": "slow",
    "fast": "fast",
    "sticky": "sticky",
    "pinned": "pinned",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def memory_import_config() -> dict[str, Any]:
    """Load optional setup.json overrides without mutating operator configuration."""
    config = {
        "enabled": True,
        "allow_zip": True,
        "allow_folder": True,
        "allow_batch_rollback": True,
        "max_single_file_mb": settings.memory_import_max_single_file_mb,
        "max_total_import_mb": settings.memory_import_max_total_mb,
        "max_files_per_import": settings.memory_import_max_files,
        "similarity_duplicate_threshold": 0.92,
        "require_preview_before_import": True,
    }
    setup_path = settings.config_path / "setup.json"
    try:
        setup = json.loads(setup_path.read_text(encoding="utf-8"))
        section = setup.get("memory_import", {})
        config["enabled"] = section.get("enabled", config["enabled"])
        config.update(section.get("openclaw_md_import", {}))
    except (OSError, ValueError, TypeError):
        pass
    return config


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else re.split(r"[,;]", str(value))
    return list(dict.fromkeys(tag for item in values if (tag := _text(item))))


def normalize_importance(value: Any, default: int = 5) -> tuple[int, str | None]:
    labels = {"low": 3, "medium": 5, "high": 8, "critical": 10}
    warning = None
    if value is None or value == "":
        return default, "Missing importance; defaulted"
    try:
        numeric = labels.get(str(value).lower())
        if numeric is None:
            numeric = float(value)
        if isinstance(numeric, float) and 0 <= numeric <= 1:
            numeric = round(numeric * 10)
        normalized = max(1, min(10, round(float(numeric))))
        if float(numeric) != normalized:
            warning = f"Importance {value!r} clamped to {normalized}"
        return normalized, warning
    except (TypeError, ValueError):
        return default, f"Invalid importance {value!r}; defaulted"


def normalize_memory_type(value: Any, default: str = "semantic") -> tuple[str, str | None]:
    incoming = _text(value).lower().replace("-", "_").replace(" ", "_")
    if not incoming:
        return default, "Missing memory type; defaulted"
    normalized = TYPE_MAP.get(incoming)
    if normalized:
        warning = None if incoming == normalized else f"Memory type {incoming!r} mapped to native type {normalized!r}"
        return normalized, warning
    return default, f"Unknown memory type {incoming!r}; defaulted to {default!r}"


def normalize_decay(value: Any, default: str = "medium") -> tuple[str, str | None]:
    incoming = _text(value).lower()
    if not incoming:
        return default, "Missing decay type; defaulted"
    normalized = DECAY_MAP.get(incoming)
    return (
        (normalized, None if normalized else f"Invalid decay type {incoming!r}; defaulted")
        if normalized
        else (default, f"Invalid decay type {incoming!r}; defaulted")
    )


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif value:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed


def content_hash(title: str, body: str) -> str:
    normalized = " ".join(f"{title}\n{body}".lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def safe_archive_name(name: str) -> bool:
    if not name or "\x00" in name:
        return False
    posix = PurePosixPath(name.replace("\\", "/"))
    windows = PureWindowsPath(name)
    return not (posix.is_absolute() or windows.is_absolute() or ".." in posix.parts or windows.drive)


def zip_info_is_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


class MarkdownMemoryParser:
    def parse(self, source_file: str, raw: bytes, *, defaults: dict[str, Any]) -> dict[str, Any]:
        warnings: list[str] = []
        text = raw.decode("utf-8", errors="replace")
        if "\ufffd" in text:
            warnings.append("Invalid UTF-8 bytes replaced during decoding")
        metadata: dict[str, Any] = {}
        match = FRONTMATTER_RE.match(text)
        if match:
            try:
                loaded = yaml.safe_load(match.group(1)) or {}
                if not isinstance(loaded, dict):
                    warnings.append("Frontmatter was not a mapping and was ignored")
                else:
                    metadata = {FIELD_SYNONYMS.get(str(k), str(k)): v for k, v in loaded.items()}
                body = text[match.end() :].strip()
            except yaml.YAMLError as exc:
                warnings.append(f"Invalid frontmatter ignored: {str(exc).splitlines()[0]}")
                body = text.strip()
        else:
            warnings.append("Missing frontmatter; metadata generated")
            body = text.strip()

        title = _text(metadata.get("title"))
        if not title:
            heading = HEADING_RE.search(body)
            first_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
            title = (heading.group(1).strip() if heading else first_line or Path(source_file).stem)[:120]
            warnings.append("Missing title; generated from content or filename")

        memory_type, warning = normalize_memory_type(metadata.get("memory_type"), defaults["memory_type"])
        if warning:
            warnings.append(warning)
        importance, warning = normalize_importance(metadata.get("importance"), defaults["importance"])
        if warning:
            warnings.append(warning)
        decay, warning = normalize_decay(
            metadata.get("decay_type", metadata.get("decay_class")), defaults["decay_type"]
        )
        if warning:
            warnings.append(warning)
        created = parse_datetime(metadata.get("created_at"))
        updated = parse_datetime(metadata.get("updated_at"))
        if not created:
            warnings.append("Missing or invalid created_at; import time will be used")
        if metadata.get("updated_at") and not updated:
            warnings.append("Invalid updated_at; import time will be used")

        try:
            confidence = max(0.0, min(1.0, float(metadata.get("confidence", 0.5) or 0.5)))
        except (TypeError, ValueError):
            confidence = 0.5
            warnings.append("Invalid confidence; defaulted")

        return {
            "source_file": source_file,
            "source_external_id": _text(metadata.get("id") or metadata.get("memory_id")) or None,
            "title": title[:500],
            "body": body,
            "memory_type": memory_type,
            "source_memory_type": _text(metadata.get("memory_type")),
            "importance": importance,
            "decay_type": decay,
            "tags": normalize_tags(metadata.get("tags")),
            "confidence": confidence,
            "source": _text(metadata.get("source")) or "openclaw_md_import",
            "source_project": _text(metadata.get("source_project")) or None,
            "source_agent": _text(metadata.get("agent")) or None,
            "created_at": created.isoformat() if created else None,
            "updated_at": updated.isoformat() if updated else None,
            "content_hash": content_hash(title, body),
            "warnings": warnings,
            "extra_metadata": {
                str(k): v
                for k, v in metadata.items()
                if str(k)
                not in {
                    "id",
                    "memory_id",
                    "title",
                    "memory_type",
                    "importance",
                    "decay_type",
                    "decay_class",
                    "tags",
                    "confidence",
                    "source",
                    "source_project",
                    "agent",
                    "created_at",
                    "updated_at",
                }
            },
        }


class MemoryImportService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.parser = MarkdownMemoryParser()

    async def preview_uploads(
        self,
        uploads: list[tuple[str, bytes]],
        *,
        agent_id: uuid.UUID,
        source_type: str = "openclaw",
        default_memory_type: str = "semantic",
        default_importance: int = 5,
        default_decay_type: str = "medium",
    ) -> MemoryImportBatch:
        if not memory_import_config()["enabled"]:
            raise ValueError("Memory import is disabled in setup.json")
        if not await self.session.get(Agent, agent_id):
            raise ValueError("Target agent does not exist")
        await self._audit(
            "memory.import.preview_started", "Started OpenClaw Markdown import preview", detail={"files": len(uploads)}
        )
        defaults = {
            "memory_type": default_memory_type,
            "importance": default_importance,
            "decay_type": default_decay_type,
        }
        batch = MemoryImportBatch(
            id=f"imp_{_now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
            source_type=source_type,
            source_name=uploads[0][0] if len(uploads) == 1 else f"{len(uploads)} uploaded sources",
            agent_id=str(agent_id),
            metadata_json={"defaults": defaults},
            warnings_json=[],
            report_json={},
        )
        self.session.add(batch)
        await self.session.flush()
        candidates = self._expand_uploads(uploads)
        batch.total_files = len(candidates)
        seen_hashes: dict[str, str] = {}
        for source_file, raw, source_error in candidates:
            item = MemoryImportItem(id=f"imi_{uuid.uuid4().hex}", batch_id=batch.id, source_file=source_file)
            if source_error:
                item.status, item.error_json = "invalid", {"message": source_error}
                batch.failed_count += 1
                self.session.add(item)
                continue
            parsed = self.parser.parse(source_file, raw, defaults=defaults)
            item.title, item.memory_type = parsed["title"], parsed["memory_type"]
            item.source_external_id, item.content_hash = parsed["source_external_id"], parsed["content_hash"]
            item.normalized_json, item.warnings_json = parsed, parsed["warnings"]
            if not parsed["body"]:
                item.status, item.error_json = "invalid", {"message": "Markdown body is empty"}
                batch.failed_count += 1
            else:
                duplicate = await self._find_duplicate(parsed)
                if parsed["content_hash"] in seen_hashes:
                    duplicate = ("batch_hash", None)
                if duplicate:
                    item.status, item.duplicate_kind, item.duplicate_memory_id = "duplicate", duplicate[0], duplicate[1]
                    duplicate_label = "Conflict" if duplicate[0].startswith("conflict") else "Duplicate"
                    await self._audit(
                        "memory.import.conflict_detected"
                        if duplicate[0].startswith("conflict")
                        else "memory.import.duplicate_detected",
                        f"{duplicate_label} detected in {source_file}",
                        batch.id,
                        item.id,
                        source_file,
                    )
                else:
                    item.status = "valid"
                    batch.valid_count += 1
                seen_hashes[parsed["content_hash"]] = item.id
            self.session.add(item)
        await self.session.flush()
        batch.warnings_json = ["Preview is required before commit; no memory rows were written"]
        await self._refresh_report(batch)
        await self._audit(
            "memory.import.preview_completed",
            f"Previewed {batch.total_files} Markdown files",
            batch.id,
            detail=batch.report_json,
        )
        return batch

    async def preview_folder(self, folder: Path, **kwargs: Any) -> MemoryImportBatch:
        if not memory_import_config()["allow_folder"]:
            raise ValueError("Local folder import is disabled in setup.json")
        root = folder.expanduser().resolve()
        if not root.is_dir():
            raise ValueError("Folder path does not exist or is not a directory")
        uploads = []
        for path in sorted(root.rglob("*.md")):
            resolved = path.resolve()
            if path.is_symlink() or not resolved.is_relative_to(root):
                continue
            uploads.append((resolved.relative_to(root).as_posix(), resolved.read_bytes()))
        return await self.preview_uploads(uploads, **kwargs)

    def _expand_uploads(self, uploads: list[tuple[str, bytes]]) -> list[tuple[str, bytes, str | None]]:
        config = memory_import_config()
        maximum = int(config["max_single_file_mb"]) * 1024 * 1024
        total_max = int(config["max_total_import_mb"]) * 1024 * 1024
        if sum(len(data) for _, data in uploads) > total_max:
            raise ValueError("Import exceeds configured total size limit")
        output: list[tuple[str, bytes, str | None]] = []
        expanded_total = 0
        for name, data in uploads:
            suffix = Path(name).suffix.lower()
            if suffix == ".md":
                expanded_total += len(data)
                safe_name = name.replace("\\", "/") if safe_archive_name(name) else Path(name).name
                output.append((safe_name, data, "File exceeds configured size limit" if len(data) > maximum else None))
            elif suffix == ".zip":
                if not config["allow_zip"]:
                    output.append((name, b"", "ZIP import is disabled in setup.json"))
                    continue
                if not zipfile.is_zipfile(io.BytesIO(data)):
                    output.append((name, b"", "Invalid ZIP archive"))
                    continue
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    for info in archive.infolist():
                        if info.is_dir() or not info.filename.lower().endswith(".md"):
                            continue
                        expanded_total += info.file_size
                        if expanded_total > total_max:
                            raise ValueError("Import exceeds configured expanded-size limit")
                        if not safe_archive_name(info.filename) or zip_info_is_symlink(info):
                            output.append((info.filename, b"", "Unsafe ZIP path rejected"))
                        elif info.file_size > maximum:
                            output.append((info.filename, b"", "File exceeds configured size limit"))
                        else:
                            output.append((info.filename.replace("\\", "/"), archive.read(info), None))
            else:
                output.append((name, b"", "Only Markdown and ZIP inputs are supported"))
            if len(output) > int(config["max_files_per_import"]):
                raise ValueError("Import exceeds configured file-count limit")
        return output

    async def _find_duplicate(self, candidate: dict[str, Any]) -> tuple[str, str | None] | None:
        conditions = [MemoryRecord.content_hash == candidate["content_hash"]]
        if candidate["source_external_id"]:
            conditions.append(MemoryRecord.source_external_id == candidate["source_external_id"])
        result = await self.session.execute(select(MemoryRecord).where(or_(*conditions)).limit(1))
        record = result.scalar_one_or_none()
        if not record:
            return None
        if candidate["source_external_id"] and record.source_external_id == candidate["source_external_id"]:
            kind = "external_id" if record.content_hash == candidate["content_hash"] else "conflict_external_id"
        else:
            kind = "content_hash"
        return kind, str(record.id)

    async def confirm(
        self, batch_id: str, *, duplicate_policy: str = "skip_exact", conflict_policy: str = "skip"
    ) -> MemoryImportBatch:
        batch = await self.get_batch(batch_id)
        if not batch:
            raise LookupError("Memory import batch not found")
        if batch.status != "previewed":
            raise ValueError(f"Batch cannot be imported from status {batch.status!r}")
        if duplicate_policy not in {"skip_exact", "import_as_new"} or conflict_policy not in {"skip", "import_as_new"}:
            raise ValueError("Unsupported duplicate or conflict policy")
        batch.status = "running"
        await self._audit("memory.import.confirmed", f"Confirmed memory import {batch.id}", batch.id)
        await self._audit("memory.import.batch_started", f"Started memory import {batch.id}", batch.id)
        items = await self._items(batch.id)
        for item in items:
            if item.status == "invalid":
                continue
            policy = conflict_policy if (item.duplicate_kind or "").startswith("conflict") else duplicate_policy
            if item.status == "duplicate" and policy in {"skip_exact", "skip"}:
                item.status = "skipped"
                batch.skipped_count += 1
                await self._audit(
                    "memory.import.item_skipped",
                    f"Skipped duplicate {item.source_file}",
                    batch.id,
                    item.id,
                    item.source_file,
                )
                continue
            candidate = item.normalized_json
            try:
                record = MemoryRecord(
                    memory_type=candidate["memory_type"],
                    agent_id=uuid.UUID(batch.agent_id),
                    title=candidate["title"],
                    content=candidate["body"],
                    relevance_score=0.7,
                    importance_score=candidate["importance"] / 10,
                    confidence_score=candidate["confidence"],
                    decay_class=candidate["decay_type"],
                    is_pinned=candidate["decay_type"] == "pinned",
                    source_type="openclaw_md_import",
                    source_system="openclaw",
                    source_file=item.source_file,
                    source_external_id=item.source_external_id,
                    import_batch_id=batch.id,
                    content_hash=item.content_hash,
                    tags=candidate["tags"],
                    created_at=parse_datetime(candidate.get("created_at")) or _now(),
                    updated_at=parse_datetime(candidate.get("updated_at")) or _now(),
                    created_by="memory_import",
                )
                self.session.add(record)
                await self.session.flush()
                item.shogun_memory_id = str(record.id)
                item.status = "imported"
                batch.imported_count += 1
                await self._audit(
                    "memory.import.item_imported",
                    f"Imported {item.source_file}",
                    batch.id,
                    item.id,
                    item.source_file,
                    str(record.id),
                )
                try:
                    await self._embed(record, candidate)
                    item.status, record.qdrant_point_id = "embedded", str(record.id)
                    batch.embedded_count += 1
                except Exception as exc:
                    item.status, item.embedding_error = "partial_failed", str(exc)
                    batch.failed_count += 1
                    await self._audit(
                        "memory.import.embedding_failed",
                        f"Embedding failed for {item.source_file}",
                        batch.id,
                        item.id,
                        item.source_file,
                        str(record.id),
                        result="failure",
                        detail={"error": str(exc)},
                    )
            except Exception as exc:
                item.status, item.error_json = "failed", {"message": str(exc)}
                batch.failed_count += 1
                await self._audit(
                    "memory.import.item_failed",
                    f"Import failed for {item.source_file}",
                    batch.id,
                    item.id,
                    item.source_file,
                    result="failure",
                    detail={"error": str(exc)},
                )
        batch.completed_at = _now()
        batch.status = "completed_with_warnings" if batch.failed_count else "completed"
        await self._refresh_report(batch)
        await self._audit(
            "memory.import.batch_completed", f"Completed memory import {batch.id}", batch.id, detail=batch.report_json
        )
        return batch

    async def _embed(self, record: MemoryRecord, candidate: dict[str, Any]) -> None:
        await self._audit(
            "memory.import.embedding_started",
            f"Embedding imported memory {record.id}",
            record.import_batch_id,
            memory_id=str(record.id),
        )
        tags = ", ".join(candidate["tags"])
        text = f"Title: {record.title}\nType: {record.memory_type}\nTags: {tags}\nContent:\n{record.content}"
        get_vector_store().upsert(
            str(record.id),
            text,
            {
                "title": record.title,
                "memory_type": record.memory_type,
                "importance_score": record.importance_score,
                "decay_class": record.decay_class,
                "tags": candidate["tags"],
                "agent_id": str(record.agent_id),
                "source_system": "openclaw",
                "source_file": record.source_file,
                "import_batch_id": record.import_batch_id,
            },
        )
        await self._audit(
            "memory.import.embedding_completed",
            f"Embedded imported memory {record.id}",
            record.import_batch_id,
            memory_id=str(record.id),
        )

    async def retry_embeddings(self, batch_id: str) -> MemoryImportBatch:
        batch = await self.get_batch(batch_id)
        if not batch:
            raise LookupError("Memory import batch not found")
        for item in await self._items(batch_id):
            if item.status != "partial_failed" or not item.shogun_memory_id:
                continue
            record = await self.session.get(MemoryRecord, uuid.UUID(item.shogun_memory_id))
            if not record:
                continue
            try:
                await self._embed(record, item.normalized_json)
                item.status, item.embedding_error, record.qdrant_point_id = "embedded", None, str(record.id)
                batch.embedded_count += 1
                batch.failed_count = max(0, batch.failed_count - 1)
            except Exception as exc:
                item.embedding_error = str(exc)
        batch.status = "completed_with_warnings" if batch.failed_count else "completed"
        await self._refresh_report(batch)
        return batch

    async def rollback(self, batch_id: str) -> MemoryImportBatch:
        if not memory_import_config()["allow_batch_rollback"]:
            raise ValueError("Memory import rollback is disabled in setup.json")
        batch = await self.get_batch(batch_id)
        if not batch:
            raise LookupError("Memory import batch not found")
        if batch.status == "rolled_back":
            raise ValueError("Batch is already rolled back")
        await self._audit("memory.import.rollback_started", f"Started rollback for {batch.id}", batch.id)
        result = await self.session.execute(select(MemoryRecord).where(MemoryRecord.import_batch_id == batch.id))
        records = list(result.scalars().all())
        for record in records:
            get_vector_store().delete_point(str(record.id))
        await self.session.execute(delete(MemoryRecord).where(MemoryRecord.import_batch_id == batch.id))
        for item in await self._items(batch.id):
            if item.shogun_memory_id:
                item.status = "rolled_back"
        batch.status, batch.completed_at = "rolled_back", _now()
        batch.report_json = {
            **(batch.report_json or {}),
            "rollback": {"removed": len(records), "at": _now().isoformat()},
        }
        await self._audit(
            "memory.import.rollback_completed",
            f"Rolled back {len(records)} imported memories",
            batch.id,
            detail={"removed": len(records)},
        )
        return batch

    async def get_batch(self, batch_id: str) -> MemoryImportBatch | None:
        return await self.session.get(MemoryImportBatch, batch_id)

    async def history(self, limit: int = 20) -> list[MemoryImportBatch]:
        result = await self.session.execute(
            select(MemoryImportBatch).order_by(MemoryImportBatch.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def _items(self, batch_id: str) -> list[MemoryImportItem]:
        result = await self.session.execute(
            select(MemoryImportItem).where(MemoryImportItem.batch_id == batch_id).order_by(MemoryImportItem.source_file)
        )
        return list(result.scalars().all())

    async def _refresh_report(self, batch: MemoryImportBatch) -> None:
        items = await self._items(batch.id)
        statuses = Counter(item.status for item in items)
        types = Counter(item.memory_type for item in items if item.memory_type)
        tags = Counter(tag for item in items for tag in (item.normalized_json or {}).get("tags", []))
        batch.report_json = {
            "batch_id": batch.id,
            "source": batch.source_name,
            "status": batch.status,
            "total_files": batch.total_files,
            "valid_memories": batch.valid_count,
            "imported_memories": batch.imported_count,
            "skipped_duplicates": batch.skipped_count,
            "failed_items": batch.failed_count,
            "embedded_memories": batch.embedded_count,
            "status_distribution": dict(statuses),
            "memory_type_distribution": dict(types),
            "tag_distribution": dict(tags.most_common(30)),
        }

    async def _audit(
        self,
        event_type: str,
        action: str,
        batch_id: str | None = None,
        item_id: str | None = None,
        source_file: str | None = None,
        memory_id: str | None = None,
        *,
        result: str = "success",
        detail: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "batch_id": batch_id,
            "item_id": item_id,
            "source_file": source_file,
            "memory_id": memory_id,
            **(detail or {}),
        }
        await EventLogger.emit(
            category="memory",
            event_type=event_type,
            action=action,
            result=result,
            user_id="local_user",
            detail=payload,
            memory_ids=[memory_id] if memory_id else [],
            db_session=self.session,
        )


def batch_response(batch: MemoryImportBatch, items: Iterable[MemoryImportItem] | None = None) -> dict[str, Any]:
    data = {
        "batch_id": batch.id,
        "source_type": batch.source_type,
        "source_name": batch.source_name,
        "agent_id": batch.agent_id,
        "status": batch.status,
        "created_at": batch.created_at,
        "completed_at": batch.completed_at,
        "total_files": batch.total_files,
        "valid_count": batch.valid_count,
        "imported_count": batch.imported_count,
        "skipped_count": batch.skipped_count,
        "failed_count": batch.failed_count,
        "embedded_count": batch.embedded_count,
        "warnings": batch.warnings_json or [],
        "report": batch.report_json or {},
    }
    if items is not None:
        data["items"] = [
            {
                "item_id": item.id,
                "source_file": item.source_file,
                "status": item.status,
                "title": item.title,
                "memory_type": item.memory_type,
                "importance": (item.normalized_json or {}).get("importance"),
                "decay_type": (item.normalized_json or {}).get("decay_type"),
                "tags": (item.normalized_json or {}).get("tags", []),
                "body_excerpt": (item.normalized_json or {}).get("body", "")[:300],
                "warnings": item.warnings_json or [],
                "error": item.error_json or {},
                "duplicate_kind": item.duplicate_kind,
                "duplicate_memory_id": item.duplicate_memory_id,
                "shogun_memory_id": item.shogun_memory_id,
                "embedding_error": item.embedding_error,
            }
            for item in items
        ]
    return data
