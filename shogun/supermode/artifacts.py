"""Validated artifact contracts and persistence for Supermode missions."""

from __future__ import annotations

import hashlib
import mimetypes
import re
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.mission import Mission
from shogun.db.models.supermode import MissionArtifact, MissionTask
from shogun.supermode.events import append_event

_CREATION_VERBS = re.compile(
    r"\b(create|deliver|export|generate|place|prepare|produce|provide|return|save|write)\w*\b",
    re.IGNORECASE,
)
_DESIRED_OUTPUT = re.compile(
    r"\b(?:need|want)\b.{0,300}\b(?:in|as)\s+(?:an?\s+)?"
    r"(?:csv|excel|markdown|microsoft\s+excel|microsoft\s+word|pdf|powerpoint|text\s+file|word)\b",
    re.IGNORECASE | re.DOTALL,
)
_OUTPUT_MARKERS = re.compile(
    r"\b(artifact|deliverable|document|file|folder|output|report|spreadsheet|workbook)\w*\b|"
    r"\.(?:csv|docx|json|md|pdf|pptx|txt|xlsx)\b",
    re.IGNORECASE,
)
_FORMAT_PATTERNS: dict[str, re.Pattern[str]] = {
    "docx": re.compile(r"\.docx\b|\b(?:in|as)\s+(?:a\s+)?(?:microsoft\s+)?word(?:\s+document)?\b", re.IGNORECASE),
    "xlsx": re.compile(
        r"\.xlsx\b|\b(?:in|as)\s+(?:an?\s+)?(?:microsoft\s+)?excel(?:\s+(?:file|workbook))?\b",
        re.IGNORECASE,
    ),
    "pptx": re.compile(r"\.pptx\b|\b(?:in|as)\s+(?:a\s+)?powerpoint(?:\s+(?:deck|presentation))?\b", re.IGNORECASE),
    "pdf": re.compile(r"\.pdf\b|\b(?:in|as)\s+(?:a\s+)?pdf\b", re.IGNORECASE),
    "csv": re.compile(r"\.csv\b|\b(?:in|as)\s+(?:a\s+)?csv\b", re.IGNORECASE),
    "text": re.compile(r"\.(?:md|txt)\b|\b(?:in|as)\s+(?:markdown|a\s+text\s+file)\b", re.IGNORECASE),
}


def mission_artifact_contract(mission: Mission) -> dict[str, Any]:
    """Derive a conservative output contract from the operator-authored mission."""
    parts = [str(mission.objective or ""), *(str(item) for item in (mission.success_criteria or []))]
    text = "\n".join(part for part in parts if part).strip()
    formats = {
        format_name
        for format_name, pattern in _FORMAT_PATTERNS.items()
        if pattern.search(text)
    }
    requires_artifacts = bool(
        (_CREATION_VERBS.search(text) and (formats or _OUTPUT_MARKERS.search(text)))
        or _DESIRED_OUTPUT.search(text)
    )
    # Default success criteria repeat the objective verbatim. Count per
    # operator-authored field and take the maximum so repetition cannot inflate
    # the required deliverable count.
    format_mentions = max(
        (sum(len(pattern.findall(part)) for pattern in _FORMAT_PATTERNS.values()) for part in parts),
        default=0,
    )
    explicit_files = max(
        (
            len(
                set(
                    match.lower()
                    for match in re.findall(
                        r"[\w][\w .()'-]{0,120}\.(?:csv|docx|json|md|pdf|pptx|txt|xlsx)\b",
                        part,
                        flags=re.IGNORECASE,
                    )
                )
            )
            for part in parts
        ),
        default=0,
    )
    criterion_outputs = sum(
        1
        for criterion in (mission.success_criteria or [])
        if any(pattern.search(str(criterion)) for pattern in _FORMAT_PATTERNS.values())
        or (_CREATION_VERBS.search(str(criterion)) and _OUTPUT_MARKERS.search(str(criterion)))
    )
    expected_count = max(format_mentions, explicit_files, criterion_outputs, 1 if requires_artifacts else 0)
    return {
        "required": requires_artifacts,
        "minimum_count": expected_count,
        "formats": sorted(formats),
    }


def output_tools_for_contract(contract: dict[str, Any]) -> list[str]:
    """Return the bounded creation tools needed by an explicit output contract."""
    if not contract.get("required"):
        return []
    tools = ["workspace_write"]
    formats = set(contract.get("formats") or [])
    if "docx" in formats:
        tools.append("office_word_create_from_text")
    if "xlsx" in formats:
        tools.append("office_excel_create")
    return tools


def _artifact_roots() -> list[Path]:
    roots = [settings.workspace_path.resolve()]
    try:
        from shogun.office.config import load_office_config

        configured_output = str(load_office_config().folders.output or "").strip()
        if configured_output:
            roots.append(Path(configured_output).resolve())
    except Exception:
        pass
    return list(dict.fromkeys(roots))


def resolve_artifact_path(descriptor: dict[str, Any]) -> Path | None:
    """Resolve a model/tool artifact descriptor without allowing path escape."""
    raw = next(
        (
            str(descriptor.get(key)).strip()
            for key in ("workspace_path", "output_file", "path", "file_path")
            if descriptor.get(key)
        ),
        "",
    )
    filename = str(descriptor.get("filename") or "").strip()
    candidates: list[Path] = []
    roots = _artifact_roots()
    if raw:
        raw_path = Path(raw)
        candidates.extend([raw_path] if raw_path.is_absolute() else [root / raw_path for root in roots])
    elif filename:
        for root in roots:
            candidates.extend([root / "output" / Path(filename).name, root / Path(filename).name])
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except (OSError, RuntimeError):
            continue
        if not any(resolved == root or root in resolved.parents for root in roots):
            continue
        if resolved.is_file():
            return resolved
    return None


def _workspace_display_path(path: Path) -> str:
    workspace_root = settings.workspace_path.resolve()
    try:
        return path.relative_to(workspace_root).as_posix()
    except ValueError:
        return str(path)


async def register_task_artifacts(
    session: AsyncSession,
    mission: Mission,
    task: MissionTask,
    descriptors: list[Any],
) -> tuple[list[MissionArtifact], list[dict[str, Any]]]:
    """Persist only descriptors that resolve to real files in an approved output root."""
    registered: list[MissionArtifact] = []
    rejected: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for raw_descriptor in descriptors[:50]:
        descriptor = raw_descriptor if isinstance(raw_descriptor, dict) else {"path": str(raw_descriptor)}
        path = resolve_artifact_path(descriptor)
        if path is None:
            rejected.append(descriptor)
            safe_descriptor = {
                key: str(descriptor[key])[:1000]
                for key in ("workspace_path", "output_file", "path", "file_path", "filename", "type")
                if descriptor.get(key)
            }
            await append_event(
                session,
                mission.id,
                "ARTIFACT_REJECTED",
                f"Rejected unverified artifact claimed by {task.title}",
                task_id=task.id,
                agent_id=task.assigned_agent_id,
                event_data={"descriptor": safe_descriptor},
                severity="warn",
            )
            continue
        canonical = str(path).casefold()
        if canonical in seen_paths:
            continue
        seen_paths.add(canonical)
        display_path = _workspace_display_path(path)
        existing = await session.scalar(
            select(MissionArtifact).where(
                MissionArtifact.mission_id == mission.id,
                MissionArtifact.workspace_path == display_path,
            )
        )
        if existing:
            registered.append(existing)
            continue
        digest = hashlib.sha256()
        with path.open("rb") as artifact_file:
            for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
                digest.update(chunk)
        mime_type = str(descriptor.get("mime_type") or "").strip() or mimetypes.guess_type(path.name)[0]
        artifact = MissionArtifact(
            mission_id=mission.id,
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            artifact_type=str(
                descriptor.get("artifact_type")
                or descriptor.get("type")
                or path.suffix.lstrip(".")
                or "file"
            )[:80],
            filename=path.name[:500],
            workspace_path=display_path[:2000],
            mime_type=mime_type[:255] if mime_type else None,
            size=path.stat().st_size,
            hash=digest.hexdigest(),
            description=str(descriptor.get("description") or descriptor.get("summary") or "")[:2000] or None,
        )
        session.add(artifact)
        await session.flush()
        registered.append(artifact)
        await append_event(
            session,
            mission.id,
            "ARTIFACT_REGISTERED",
            f"Registered mission artifact: {artifact.filename}",
            task_id=task.id,
            agent_id=task.assigned_agent_id,
            event_data={"artifact_id": str(artifact.id), "workspace_path": artifact.workspace_path},
        )
    return registered, rejected


def artifact_record_payload(artifact: MissionArtifact) -> dict[str, Any]:
    return {
        "artifact_id": str(artifact.id),
        "type": artifact.artifact_type,
        "filename": artifact.filename,
        "workspace_path": artifact.workspace_path,
        "mime_type": artifact.mime_type,
        "size": artifact.size,
        "hash": artifact.hash,
        "description": artifact.description,
    }
