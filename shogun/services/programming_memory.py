"""Project-scoped, evidence-aware memory for programming work."""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.programming_memory import ProgrammingMemory

VALID_KINDS = {"solution", "correction", "pattern", "project_fact", "failed_approach"}
VALIDATIONS = {"unverified", "operator_confirmed", "tests_passed", "production_confirmed"}
VALIDATION_RANK = {"unverified": 0, "operator_confirmed": 1, "tests_passed": 2, "production_confirmed": 3}


class ProgrammingMemoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def workspace_key(root: str | Path) -> str:
        normalized = os.path.normcase(str(Path(root).expanduser().resolve(strict=False)))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def content_hash(problem: str, solution: str) -> str:
        normalized = " ".join(f"{problem}\n{solution}".lower().split())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def remember(
        self,
        *,
        agent_id: uuid.UUID,
        workspace_key: str,
        workspace_name: str,
        title: str,
        problem: str,
        solution: str,
        kind: str = "solution",
        evidence: str | None = None,
        validation_status: str = "unverified",
        confidence_score: float = 0.7,
        languages: list[str] | None = None,
        files: list[str] | None = None,
        source_urls: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> tuple[ProgrammingMemory, bool]:
        if kind not in VALID_KINDS:
            raise ValueError(f"Unsupported programming memory kind: {kind}")
        if validation_status not in VALIDATIONS:
            raise ValueError(f"Unsupported validation status: {validation_status}")
        if not problem.strip() or not solution.strip():
            raise ValueError("Programming memory requires both a problem and a solution.")
        digest = self.content_hash(problem, solution)
        existing = await self.session.scalar(
            select(ProgrammingMemory).where(
                ProgrammingMemory.workspace_key == workspace_key,
                ProgrammingMemory.content_hash == digest,
            )
        )
        if existing:
            existing.evidence = evidence or existing.evidence
            if VALIDATION_RANK[validation_status] > VALIDATION_RANK[existing.validation_status]:
                existing.validation_status = validation_status
            existing.confidence_score = max(existing.confidence_score, min(max(confidence_score, 0.0), 1.0))
            existing.languages = sorted(set(existing.languages or []) | set(languages or []))
            existing.files = sorted(set(existing.files or []) | set(files or []))
            existing.source_urls = sorted(set(existing.source_urls or []) | set(source_urls or []))
            existing.tags = sorted(set(existing.tags or []) | set(tags or []))
            await self.session.flush()
            return existing, False

        record = ProgrammingMemory(
            agent_id=agent_id,
            workspace_key=workspace_key,
            workspace_name=workspace_name,
            kind=kind,
            title=title[:500],
            problem=problem,
            solution=solution,
            evidence=evidence,
            validation_status=validation_status,
            confidence_score=min(max(confidence_score, 0.0), 1.0),
            languages=sorted(set(languages or [])),
            files=sorted(set(files or [])),
            source_urls=sorted(set(source_urls or [])),
            tags=sorted(set(tags or [])),
            content_hash=digest,
        )
        self.session.add(record)
        await self.session.flush()
        return record, True

    async def search(
        self,
        *,
        workspace_key: str,
        query: str,
        limit: int = 8,
        include_global: bool = False,
    ) -> list[dict[str, Any]]:
        scope = ProgrammingMemory.workspace_key == workspace_key
        if include_global:
            scope = or_(scope, ProgrammingMemory.workspace_key == "global")
        records = list((await self.session.scalars(select(ProgrammingMemory).where(scope).limit(500))).all())
        query_terms = set(re.findall(r"[a-zA-Z0-9_+#.-]{2,}", query.lower()))

        def score(record: ProgrammingMemory) -> float:
            haystack = " ".join(
                [
                    record.title,
                    record.problem,
                    record.solution,
                    *(record.languages or []),
                    *(record.files or []),
                    *(record.tags or []),
                ]
            ).lower()
            terms = set(re.findall(r"[a-zA-Z0-9_+#.-]{2,}", haystack))
            overlap = len(query_terms & terms) / max(len(query_terms), 1)
            validation = {"production_confirmed": 0.25, "tests_passed": 0.2, "operator_confirmed": 0.15}.get(
                record.validation_status, 0.0
            )
            reuse = min(record.successful_use_count * 0.03, 0.15)
            return overlap * 0.6 + record.confidence_score * 0.25 + validation + reuse

        ranked = sorted(records, key=score, reverse=True)[: max(1, min(limit, 50))]
        now = datetime.now(timezone.utc)
        for record in ranked:
            record.use_count += 1
            record.last_used_at = now
        await self.session.flush()
        return [{**self.serialize(record), "match_score": round(score(record), 4)} for record in ranked]

    async def reinforce(
        self,
        memory_id: uuid.UUID,
        *,
        successful: bool = True,
        workspace_key: str | None = None,
    ) -> ProgrammingMemory | None:
        record = await self.session.get(ProgrammingMemory, memory_id)
        if not record or (workspace_key is not None and record.workspace_key != workspace_key):
            return None
        record.use_count += 1
        if successful:
            record.successful_use_count += 1
            record.confidence_score = min(1.0, record.confidence_score + 0.05)
        else:
            record.confidence_score = max(0.0, record.confidence_score - 0.08)
        record.last_used_at = datetime.now(timezone.utc)
        await self.session.flush()
        return record

    @staticmethod
    def serialize(record: ProgrammingMemory) -> dict[str, Any]:
        return {
            "id": str(record.id),
            "agent_id": str(record.agent_id),
            "workspace_key": record.workspace_key,
            "workspace_name": record.workspace_name,
            "kind": record.kind,
            "title": record.title,
            "problem": record.problem,
            "solution": record.solution,
            "evidence": record.evidence,
            "validation_status": record.validation_status,
            "confidence_score": record.confidence_score,
            "languages": record.languages or [],
            "files": record.files or [],
            "source_urls": record.source_urls or [],
            "tags": record.tags or [],
            "use_count": record.use_count,
            "successful_use_count": record.successful_use_count,
            "last_used_at": record.last_used_at,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
            "content_hash": record.content_hash,
        }
