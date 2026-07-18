"""Order 16: export Shogun memory into portable OpenClaw-style Markdown bundles."""

from __future__ import annotations

import json
import re
import uuid
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.agent import Agent
from shogun.db.models.memory_export import MemoryExportItem, MemoryExportJob
from shogun.db.models.memory_record import MemoryProvenanceLink, MemoryRecord
from shogun.schemas.memory import MemoryExportRequest
from shogun.services.event_logger import EventLogger

SCHEMA_VERSION = "1.0"
SECRET_MARKERS = ("secret", "credential", "password", "token", "api_key", "private_key")
PRIVATE_MARKERS = ("private", "confidential", "personal")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _yaml_scalar(value: Any) -> str:
    """Render a JSON scalar, which is also valid and injection-safe YAML 1.2."""
    if isinstance(value, datetime):
        value = _iso(value)
    return json.dumps(value, ensure_ascii=False, default=str)


def render_frontmatter(metadata: dict[str, Any]) -> str:
    lines = ["---"]
    for key, value in metadata.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                lines.extend(f"  - {_yaml_scalar(item)}" for item in value)
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def safe_filename(record: MemoryRecord) -> str:
    title = re.sub(r"[^a-z0-9]+", "-", (record.title or "memory").lower()).strip("-")
    title = title[:60].rstrip("-") or "memory"
    memory_type = re.sub(r"[^a-z0-9]+", "-", record.memory_type.lower()).strip("-") or "memory"
    created = (record.created_at or _utc_now()).date().isoformat()
    short_id = str(record.id).replace("-", "")[:10]
    filename = f"{memory_type}_{created}_{short_id}_{title}.md"
    return filename[:116].rstrip(".-_") + ".md" if len(filename) > 120 else filename


def _visibility(record: MemoryRecord) -> str:
    source = (record.source_type or "").lower()
    if record.memory_type == "persona" or record.is_pinned or any(marker in source for marker in PRIVATE_MARKERS):
        return "private"
    return "internal"


def _is_secret(record: MemoryRecord) -> bool:
    classification = f"{record.memory_type} {record.source_type or ''} {record.title}".lower()
    return any(marker in classification for marker in SECRET_MARKERS)


def _is_analysis(record: MemoryRecord) -> bool:
    return record.memory_type == "analysis" or "analysis" in (record.source_type or "").lower()


def _is_sticky(record: MemoryRecord) -> bool:
    return record.is_pinned or record.decay_class in {"sticky", "pinned"}


def _record_json(record: MemoryRecord) -> dict[str, Any]:
    return {
        column.name: getattr(record, column.name)
        for column in record.__table__.columns
    }


class MemoryMarkdownRenderer:
    """Convert a memory record into stable, human-readable Markdown."""

    def render(
        self,
        record: MemoryRecord,
        *,
        exported_at: datetime,
        agent_name: str | None = None,
        related_ids: list[str] | None = None,
    ) -> str:
        archived = bool(record.is_archived)
        related = related_ids or []
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "export_type": "shogun_archive" if archived else "shogun_memory",
            "memory_id": str(record.id),
            "source_system": "shogun_afm",
            "target_compatibility": "openclaw_md",
            "title": record.title,
            "memory_type": record.memory_type,
            "agent_id": str(record.agent_id) if record.agent_id else None,
            "project_id": self._project_id(record),
            "importance": record.importance_score,
            "confidence": record.confidence_score,
            "decay_type": record.decay_class,
            "tags": [],
            "visibility": _visibility(record),
            "source_table": "memory_records",
            "source_record_id": str(record.id),
            "origin": record.source_type,
            "run_id": self._source_id(record, "run"),
            "stack_run_id": self._source_id(record, "stack"),
            "skill_id": self._source_id(record, "skill"),
            "related_memory_ids": related,
            "last_accessed_at": _iso(record.last_accessed_at),
            "access_count": record.access_count,
            "created_at": _iso(record.created_at),
            "updated_at": _iso(record.updated_at),
            "exported_at": _iso(exported_at),
        }
        if archived:
            metadata["archive_id"] = str(record.id)
            metadata["archive_type"] = record.memory_type

        title = (record.title or "Untitled memory").replace("\n", " ").strip()
        body = [render_frontmatter(metadata), "", f"# {title}", "", record.content or record.summary or ""]
        readable = [
            ("Memory type", record.memory_type),
            ("Importance", record.importance_score),
            ("Confidence", record.confidence_score),
            ("Decay type", record.decay_class),
            ("Agent", agent_name or str(record.agent_id)),
            ("Project", self._project_id(record)),
            ("Created", _iso(record.created_at)),
            ("Updated", _iso(record.updated_at)),
        ]
        body.extend(["", "## Metadata", ""])
        body.extend(f"- {label}: {value}" for label, value in readable if value is not None)
        body.extend(["", "## Source Trace", ""])
        body.append(
            f"Originally stored in Shogun Archives. Source: {record.source_type or 'memory_records'}."
            if archived
            else f"Originally stored in Shogun memory. Source: {record.source_type or 'memory_records'}."
        )
        if related:
            body.extend(["", "## Related", ""])
            body.extend(f"- {item}" for item in related)
        return "\n".join(body).rstrip() + "\n"

    @staticmethod
    def _project_id(record: MemoryRecord) -> str | None:
        source = record.source_type or ""
        if source.startswith("project:"):
            return source.split(":", 1)[1]
        if source == "project" and record.source_ref_id:
            return str(record.source_ref_id)
        return None

    @staticmethod
    def _source_id(record: MemoryRecord, source_kind: str) -> str | None:
        source = (record.source_type or "").lower()
        if source.startswith(f"{source_kind}:"):
            return source.split(":", 1)[1]
        if source_kind in source and record.source_ref_id:
            return str(record.source_ref_id)
        return None


class MemoryExportService:
    def __init__(self, session: AsyncSession, export_root: Path | None = None):
        self.session = session
        self.export_root = (export_root or settings.memory_exports_path).resolve()
        self.renderer = MemoryMarkdownRenderer()

    async def preview(self, request: MemoryExportRequest) -> dict[str, Any]:
        records = await self._query_records(request)
        counts = self._counts(records)
        warnings = self._warnings(request, records)
        return {
            "estimated_counts": counts,
            "warnings": warnings,
            "filters": request.model_dump(mode="json", exclude={"private_export_confirmed"}),
        }

    async def create_job(self, request: MemoryExportRequest, requested_by: str = "local_user") -> MemoryExportJob:
        if (request.include_private or request.include_secrets) and not request.private_export_confirmed:
            raise ValueError("Sensitive-memory export requires explicit confirmation")
        export_id = f"exp_{_utc_now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        job = MemoryExportJob(
            id=export_id,
            status="pending",
            requested_by=requested_by,
            filters_json=request.model_dump(mode="json"),
            counts_json={},
            error_json={},
            metadata_json={"schema_version": SCHEMA_VERSION, "warnings": []},
        )
        self.session.add(job)
        await self.session.flush()
        return job

    async def execute(self, export_id: str) -> MemoryExportJob:
        job = await self.session.get(MemoryExportJob, export_id)
        if not job:
            raise LookupError("Memory export job not found")
        if job.status == "cancelled":
            return job
        request = MemoryExportRequest.model_validate(job.filters_json)
        job.status = "running"
        job.started_at = _utc_now()
        await self.session.commit()
        await EventLogger.emit(
            category="memory",
            event_type="memory.export.started",
            action=f"Started memory export {export_id}",
            user_id=job.requested_by,
            data_classification="private" if request.include_private else "internal",
            detail={"export_id": export_id, "filters": job.filters_json},
        )
        try:
            records = await self._query_records(request)
            await self._build_bundle(job, request, records)
            await self.session.commit()
            await EventLogger.emit(
                category="memory",
                event_type="memory.export.completed",
                action=f"Completed memory export {export_id}",
                user_id=job.requested_by,
                data_classification="private" if request.include_private else "internal",
                detail={"export_id": export_id, "counts": job.counts_json, "status": job.status},
                memory_ids=[str(record.id) for record in records],
            )
        except Exception as exc:
            job.status = "failed"
            job.completed_at = _utc_now()
            job.error_json = {"message": str(exc), "type": type(exc).__name__}
            await self.session.commit()
            await EventLogger.emit(
                category="memory",
                event_type="memory.export.failed",
                action=f"Memory export {export_id} failed",
                result="failure",
                severity="error",
                user_id=job.requested_by,
                detail={"export_id": export_id, "error": job.error_json},
            )
        return job

    async def get_job(self, export_id: str) -> MemoryExportJob | None:
        return await self.session.get(MemoryExportJob, export_id)

    async def history(self, limit: int = 20) -> list[MemoryExportJob]:
        result = await self.session.execute(
            select(MemoryExportJob).order_by(MemoryExportJob.requested_at.desc()).limit(max(1, min(limit, 100)))
        )
        return list(result.scalars().all())

    async def cancel(self, export_id: str) -> MemoryExportJob:
        job = await self.session.get(MemoryExportJob, export_id)
        if not job:
            raise LookupError("Memory export job not found")
        if job.status != "pending":
            raise ValueError(f"Only pending exports can be cancelled (current status: {job.status})")
        job.status = "cancelled"
        job.completed_at = _utc_now()
        await self.session.commit()
        await EventLogger.emit(
            category="memory",
            event_type="memory.export.cancelled",
            action=f"Cancelled memory export {export_id}",
            user_id=job.requested_by,
            detail={"export_id": export_id},
        )
        return job

    def download_path(self, job: MemoryExportJob) -> Path:
        if job.status not in {"completed", "completed_with_warnings"} or not job.zip_path:
            raise ValueError("Export ZIP is not available")
        path = Path(job.zip_path).resolve()
        if path.parent != self.export_root or path.suffix.lower() != ".zip":
            raise ValueError("Export path is outside controlled storage")
        if path.name != f"{job.id}.zip" or not path.is_file():
            raise ValueError("Export ZIP does not exist")
        return path

    async def _query_records(self, request: MemoryExportRequest) -> list[MemoryRecord]:
        filters = []
        if request.scope == "archives":
            filters.append(MemoryRecord.is_archived.is_(True))
        elif not request.include_archives:
            filters.append(MemoryRecord.is_archived.is_(False))
        if request.agent_id:
            filters.append(MemoryRecord.agent_id == request.agent_id)
        if request.memory_types:
            filters.append(MemoryRecord.memory_type.in_(request.memory_types))
        if request.decay_classes:
            filters.append(MemoryRecord.decay_class.in_(request.decay_classes))
        if request.date_from:
            filters.append(MemoryRecord.created_at >= request.date_from)
        if request.date_to:
            filters.append(MemoryRecord.created_at <= request.date_to)
        if request.min_importance is not None:
            filters.append(MemoryRecord.importance_score >= request.min_importance)
        if request.project_id:
            project = request.project_id.strip()
            candidates = [MemoryRecord.source_type == project, MemoryRecord.source_type == f"project:{project}"]
            try:
                candidates.append(MemoryRecord.source_ref_id == uuid.UUID(project))
            except ValueError:
                pass
            filters.append(or_(*candidates))
        if request.source_run_id:
            filters.append(self._source_filter("run", request.source_run_id))
        if request.stack_run_id:
            filters.append(self._source_filter("stack", request.stack_run_id))
        if request.skill_id:
            filters.append(self._source_filter("skill", request.skill_id))

        query = select(MemoryRecord).order_by(MemoryRecord.created_at.asc(), MemoryRecord.id.asc())
        if filters:
            query = query.where(and_(*filters))
        records = list((await self.session.execute(query)).scalars().all())
        return [
            record for record in records
            if (request.include_private or _visibility(record) != "private")
            and (request.include_sticky or not _is_sticky(record))
            and (request.include_analysis or not _is_analysis(record))
            and (request.include_secrets or not _is_secret(record))
        ]

    async def _build_bundle(
        self,
        job: MemoryExportJob,
        request: MemoryExportRequest,
        records: list[MemoryRecord],
    ) -> None:
        self.export_root.mkdir(parents=True, exist_ok=True)
        bundle_dir = (self.export_root / job.id).resolve()
        if bundle_dir.parent != self.export_root:
            raise ValueError("Invalid export directory")
        bundle_dir.mkdir(parents=False, exist_ok=False)
        exported_at = _utc_now()
        notices = self._warnings(request, records)
        item_warnings: list[str] = []
        files: list[dict[str, Any]] = []

        agent_ids = {record.agent_id for record in records if record.agent_id}
        agents: dict[uuid.UUID, str] = {}
        if agent_ids:
            result = await self.session.execute(select(Agent).where(Agent.id.in_(agent_ids)))
            agents = {agent.id: agent.name for agent in result.scalars().all()}
        related = await self._related_map(records)

        for record in records:
            source_kind = "archive" if record.is_archived else "memory"
            category = re.sub(r"[^a-z0-9_-]+", "-", record.memory_type.lower()).strip("-") or "general"
            relative = Path("archives" if record.is_archived else "memories") / category / safe_filename(record)
            target = (bundle_dir / relative).resolve()
            if bundle_dir not in target.parents:
                raise ValueError("Unsafe export item path")
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                target.write_text(
                    self.renderer.render(
                        record,
                        exported_at=exported_at,
                        agent_name=agents.get(record.agent_id),
                        related_ids=related.get(str(record.id), []),
                    ),
                    encoding="utf-8",
                    newline="\n",
                )
                item = MemoryExportItem(
                    id=f"item_{uuid.uuid4().hex}",
                    export_job_id=job.id,
                    source_type=source_kind,
                    source_id=str(record.id),
                    output_path=relative.as_posix(),
                    title=record.title,
                    metadata_json={"memory_type": record.memory_type},
                )
                self.session.add(item)
                files.append({
                    "path": relative.as_posix(),
                    "memory_id": str(record.id),
                    "title": record.title,
                    "memory_type": record.memory_type,
                    "export_type": f"shogun_{source_kind}",
                })
            except Exception as exc:
                item_warnings.append(f"Skipped {record.id}: {exc}")
                self.session.add(MemoryExportItem(
                    id=f"item_{uuid.uuid4().hex}",
                    export_job_id=job.id,
                    source_type=source_kind,
                    source_id=str(record.id),
                    output_path=relative.as_posix(),
                    title=record.title,
                    metadata_json={"memory_type": record.memory_type, "status": "failed"},
                    error=str(exc),
                ))

        counts = self._counts(records)
        counts["files"] = len(files)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "export_type": "shogun_memory_bundle",
            "source_system": "shogun_afm",
            "target_compatibility": "openclaw_md",
            "export_id": job.id,
            "exported_at": _iso(exported_at),
            "exported_by": job.requested_by,
            "counts": counts,
            "filters": request.model_dump(mode="json", exclude={"private_export_confirmed"}),
            "warnings": notices + item_warnings,
            "files": files,
        }
        (bundle_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
        )
        (bundle_dir / "README.md").write_text(
            self._readme(job.id, exported_at, counts, request, notices + item_warnings),
            encoding="utf-8",
            newline="\n",
        )
        (bundle_dir / "export_report.md").write_text(
            self._report(counts, notices + item_warnings), encoding="utf-8", newline="\n"
        )
        if request.include_raw_json:
            raw = bundle_dir / "raw"
            raw.mkdir()
            active = [_record_json(record) for record in records if not record.is_archived]
            archived = [_record_json(record) for record in records if record.is_archived]
            (raw / "memories.json").write_text(
                json.dumps(active, ensure_ascii=False, indent=2, default=str), encoding="utf-8", newline="\n"
            )
            (raw / "archives.json").write_text(
                json.dumps(archived, ensure_ascii=False, indent=2, default=str), encoding="utf-8", newline="\n"
            )

        zip_path = None
        if request.package_as_zip:
            zip_path = self.export_root / f"{job.id}.zip"
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for file_path in sorted(path for path in bundle_dir.rglob("*") if path.is_file()):
                    archive.write(file_path, file_path.relative_to(bundle_dir).as_posix())

        job.status = "completed_with_warnings" if item_warnings else "completed"
        job.completed_at = _utc_now()
        job.counts_json = counts
        job.output_dir = str(bundle_dir)
        job.zip_path = str(zip_path) if zip_path else None
        job.metadata_json = {
            "schema_version": SCHEMA_VERSION,
            "warnings": notices + item_warnings,
            "files": len(files),
        }

    async def _related_map(self, records: list[MemoryRecord]) -> dict[str, list[str]]:
        ids = [record.id for record in records]
        related: dict[str, set[str]] = defaultdict(set)
        if not ids:
            return {}
        result = await self.session.execute(
            select(MemoryProvenanceLink).where(
                or_(
                    MemoryProvenanceLink.child_memory_id.in_(ids),
                    MemoryProvenanceLink.parent_memory_id.in_(ids),
                )
            )
        )
        for link in result.scalars().all():
            related[str(link.child_memory_id)].add(str(link.parent_memory_id))
            related[str(link.parent_memory_id)].add(str(link.child_memory_id))
        return {key: sorted(values) for key, values in related.items()}

    @staticmethod
    def _source_filter(source_kind: str, source_id: str):
        candidates = [
            MemoryRecord.source_type == f"{source_kind}:{source_id}",
        ]
        try:
            candidates.append(and_(
                MemoryRecord.source_type.like(f"%{source_kind}%"),
                MemoryRecord.source_ref_id == uuid.UUID(source_id),
            ))
        except ValueError:
            pass
        return or_(*candidates)

    @staticmethod
    def _counts(records: list[MemoryRecord]) -> dict[str, int]:
        return {
            "memories": sum(not record.is_archived for record in records),
            "archives": sum(record.is_archived for record in records),
            "sticky": sum(_is_sticky(record) for record in records),
            "analysis": sum(_is_analysis(record) for record in records),
            "private": sum(_visibility(record) == "private" for record in records),
            "skills": sum(record.memory_type == "skills" for record in records),
            "trajectories": 0,
            "total": len(records),
        }

    @staticmethod
    def _warnings(request: MemoryExportRequest, records: list[MemoryRecord]) -> list[str]:
        warnings = []
        if request.include_private:
            warnings.append("Private memories are included. Store this export securely.")
        if not request.include_secrets:
            warnings.append("Secret-classified records were excluded by default.")
        if not records:
            warnings.append("No records matched the selected filters.")
        return warnings

    @staticmethod
    def _readme(
        export_id: str,
        exported_at: datetime,
        counts: dict[str, int],
        request: MemoryExportRequest,
        warnings: list[str],
    ) -> str:
        lines = [
            "# Shogun Memory Export",
            "",
            "This bundle contains portable memory and archive records exported from Shogun AFM.",
            "",
            f"- Export ID: {export_id}",
            f"- Exported at: {_iso(exported_at)}",
            "- Source system: Shogun AFM",
            "- Target compatibility: OpenClaw MD",
            f"- Total memories: {counts['memories']}",
            f"- Total archives: {counts['archives']}",
            f"- Raw JSON included: {'Yes' if request.include_raw_json else 'No'}",
            "",
            "## Filters",
            "",
            f"- Scope: {request.scope}",
            f"- Agent: {request.agent_id or 'all'}",
            f"- Project: {request.project_id or 'all'}",
            f"- Memory types: {', '.join(request.memory_types) if request.memory_types else 'all'}",
            f"- Date from: {_iso(request.date_from) or 'unbounded'}",
            f"- Date to: {_iso(request.date_to) or 'unbounded'}",
            f"- Private records: {'included' if request.include_private else 'excluded'}",
            f"- Secret-classified records: {'included' if request.include_secrets else 'excluded'}",
            "",
            (
                "`manifest.json` is the machine-readable index. Each `.md` file contains "
                "YAML frontmatter and readable content."
            ),
            "",
            "## Warning",
            "",
            (
                "This export may contain private user context, project information, preferences, "
                "and operational notes. Store it securely."
            ),
        ]
        if warnings:
            lines.extend(["", "## Export Notes", "", *(f"- {warning}" for warning in warnings)])
        return "\n".join(lines) + "\n"

    @staticmethod
    def _report(counts: dict[str, int], warnings: list[str]) -> str:
        lines = [
            "# Export Report",
            "",
            *(f"- {key.replace('_', ' ').title()}: {value}" for key, value in counts.items()),
        ]
        if warnings:
            lines.extend(["", "## Warnings", "", *(f"- {warning}" for warning in warnings)])
        return "\n".join(lines) + "\n"


def job_response(job: MemoryExportJob) -> dict[str, Any]:
    counts = job.counts_json or {}
    return {
        "export_id": job.id,
        "status": job.status,
        "requested_at": job.requested_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "records_exported": counts.get("files", counts.get("total", 0)),
        "counts": counts,
        "warnings": (job.metadata_json or {}).get("warnings", []),
        "error": job.error_json or {},
        "download_url": (
            f"/api/v1/memory/export/{job.id}/download"
            if job.status in {"completed", "completed_with_warnings"} and job.zip_path
            else None
        ),
    }
