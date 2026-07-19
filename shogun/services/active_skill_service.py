"""Order 9 active-skill retrieval, policy gating, injection, and outcomes."""

from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.active_skill_run import ActiveSkillRun
from shogun.db.models.memory_record import MemoryRecord
from shogun.db.models.skill import Skill
from shogun.db.models.skill_installation import SkillInstallation
from shogun.schemas.skills import SkillActivationRequest
from shogun.services.event_logger import EventLogger

logger = logging.getLogger(__name__)

POSTURE_RANK = {
    "locked": 0,
    "shrine": 0,
    "guarded": 1,
    "supervised": 2,
    "tactical": 2,
    "campaign": 3,
    "ronin": 4,
}
RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}
POSTURE_RISK_CEILING = {0: 0, 1: 1, 2: 2, 3: 3, 4: 3}
OUTCOMES = {"success", "partial", "failed", "not_used", "blocked", "unknown"}


def _tokens(text: str) -> set[str]:
    return {item for item in re.findall(r"[a-z0-9_+-]{3,}", (text or "").lower())}


def _estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def _truncate_tokens(text: str, limit: int) -> str:
    if _estimate_tokens(text) <= limit:
        return text
    suffix = "\n[skill brief truncated]"
    result = text[: max(0, limit * 4 - len(suffix))].rstrip() + suffix
    while result and _estimate_tokens(result) > limit:
        result = result[:-1]
    return result


class SkillMetadataService:
    """Normalize legacy manifest fields into the Order 9 schema."""

    @staticmethod
    def normalize(skill: Skill) -> None:
        manifest = dict(skill.manifest or {})
        list_fields = ("tags", "triggers", "use_when", "avoid_when", "requires_tools")
        for field in list_fields:
            current = getattr(skill, field, None) or []
            if not current:
                value = manifest.get(field, [])
                setattr(skill, field, value if isinstance(value, list) else [str(value)])
        scalar_defaults = {
            "minimum_posture": "guarded",
            "risk_tier": "low",
            "priority": 50,
            "conflict_group": None,
            "model_hint": None,
            "activation_mode": "advisory",
        }
        for field, default in scalar_defaults.items():
            if getattr(skill, field, None) in (None, ""):
                setattr(skill, field, manifest.get(field, default))


class SkillContextComposer:
    @staticmethod
    def default_brief(skill: Skill) -> str:
        manifest = skill.manifest or {}
        purpose = manifest.get("description") or manifest.get("purpose") or skill.name
        use_when = skill.use_when or skill.triggers or skill.tags
        avoid = skill.avoid_when or []
        procedure = manifest.get("procedure") or manifest.get("instructions") or []
        if isinstance(procedure, str):
            procedure_text = procedure.strip()
        else:
            procedure_text = "\n".join(f"{idx}. {item}" for idx, item in enumerate(procedure, 1))
        checklist = skill.verification_checklist or manifest.get("verification_checklist") or []
        chunks = [
            f"ACTIVE SKILL: {skill.name}",
            f"Purpose: {purpose}",
            "Use for: " + ("; ".join(map(str, use_when)) if use_when else "tasks matching this capability"),
        ]
        if avoid:
            chunks.append("Do not use for: " + "; ".join(map(str, avoid)))
        if procedure_text:
            chunks.append("Key procedure:\n" + procedure_text)
        if checklist:
            chunks.append("Verification: " + "; ".join(map(str, checklist)))
        if skill.risk_tier in {"high", "critical"}:
            chunks.append(f"Risk note: {skill.risk_tier} risk; posture and tool permissions remain authoritative.")
        return "\n".join(chunks)

    @classmethod
    def compose(cls, selected: list[dict[str, Any]], budget: int, all_skills: list[Skill] = None) -> tuple[str, int]:
        blocks: list[str] = []
        used = 0
        for candidate in selected:
            skill: Skill = candidate["skill"]
            archive_content = candidate.get("archive_content")
            if archive_content:
                brief = (
                    f"ACTIVE SKILL: {skill.name}\n"
                    "CANONICAL ARCHIVES INSTRUCTIONS:\n"
                    f"{archive_content}"
                )
            else:
                brief = skill.brief_text or cls.default_brief(skill)
            per_skill = min(skill.max_context_tokens or settings.active_skill_default_context_tokens, budget - used)
            if per_skill <= 0:
                candidate["brief"] = ""
                candidate["injected_tokens"] = 0
                continue
            brief = _truncate_tokens(brief, per_skill)
            injected = _estimate_tokens(brief)
            candidate["brief"] = brief
            candidate["injected_tokens"] = injected
            used += injected
            blocks.append(brief)

        header = (
            "SKILL AWARENESS PROTOCOL:\n"
            "Archives semantic memory was searched for this task before execution.\n"
            "Follow each retrieved skill's procedure and verification checklist.\n"
            "If multiple skills apply, combine their guidance. Skills do not grant tools or permissions.\n"
            "After completing a task, note which skills were used.\n\n"
            "ACTIVE SKILLS FOR THIS RUN\n"
            "Apply these compact, validated procedures."
        )

        main_block = header + "\n\n" + "\n\n---\n\n".join(blocks) if blocks else ""

        if all_skills and main_block:
            main_block += (
                f"\n\nArchives retrieval evaluated {len(all_skills)} available skills "
                f"and injected the {len(selected)} most relevant within the context budget."
            )

        return main_block, used


class SkillEmbeddingService:
    """Optional Qdrant semantic layer; metadata retrieval remains available offline."""

    @staticmethod
    async def index(skill: Skill) -> str:
        from shogun.engine.vector_store import get_vector_store

        text = "\n".join(
            [skill.name, skill.brief_text or "", " ".join(skill.tags or []), " ".join(skill.triggers or [])]
        )
        store = get_vector_store()
        await asyncio.to_thread(store.ensure_collection)
        await asyncio.to_thread(
            store.upsert,
            str(skill.id),
            text,
            {"memory_type": "skill", "skill_id": str(skill.id), "title": skill.name},
        )
        skill.embedding_id = str(skill.id)
        return str(skill.id)

    @staticmethod
    async def search(query: str, limit: int = 20) -> dict[str, float]:
        from shogun.engine.vector_store import get_vector_store

        try:
            hits = await asyncio.to_thread(
                get_vector_store().search, query, memory_types=["skills", "skill"], limit=limit
            )
            scores: dict[str, float] = {}
            for hit in hits:
                payload = hit.get("payload") or {}
                skill_id = payload.get("skill_id") or payload.get("source_ref_id")
                if skill_id:
                    scores[str(skill_id)] = max(scores.get(str(skill_id), 0.0), float(hit["score"]))
            return scores
        except Exception as exc:
            logger.debug("Skill semantic search unavailable; using metadata retrieval: %s", exc)
            return {}


class SkillHierarchyService:
    """Cached top-down retrieval across specializations, bundles, then skills."""

    _cache: tuple[list[dict[str, Any]], list[dict[str, Any]]] | None = None
    _cache_at: float = 0.0
    cache_ttl_seconds: float = 15 * 60
    # Hierarchy is an accelerator/reranker, never a reason to hold up a task.
    fetch_timeout_seconds: float = 3.0
    generic_tokens = {
        "advanced", "specialization", "bundle", "skill", "skills", "professional",
        "management", "agent", "agents", "task", "tasks", "general", "spec",
    }

    @classmethod
    async def _catalog(cls) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if cls._cache is not None and time.monotonic() - cls._cache_at < cls.cache_ttl_seconds:
            return cls._cache

        from shogun.integrations.openclaw_client import get_openclaw_client

        async def fetch() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            async with get_openclaw_client() as client:
                bundle_response, specialization_response = await asyncio.gather(
                    client.client.get(f"{client.base_url}/bundles"),
                    client.client.get(f"{client.base_url}/specializations"),
                )
                bundle_response.raise_for_status()
                specialization_response.raise_for_status()
                return bundle_response.json(), specialization_response.json()

        try:
            cls._cache = await asyncio.wait_for(fetch(), timeout=cls.fetch_timeout_seconds)
            cls._cache_at = time.monotonic()
            return cls._cache
        except Exception as exc:
            logger.debug("Skill hierarchy unavailable; direct retrieval remains active: %s", exc)
            return [], []

    @classmethod
    def _relevance(cls, query_tokens: set[str], item: dict[str, Any]) -> float:
        text = " ".join(str(item.get(field) or "") for field in (
            "name", "title", "description", "shortDescription", "facultyId", "categoryId", "slug",
        ))
        item_tokens = _tokens(text) - cls.generic_tokens
        useful_query = query_tokens - cls.generic_tokens
        if not useful_query or not item_tokens:
            return 0.0
        overlap = useful_query & item_tokens
        if not overlap:
            return 0.0
        coverage = len(overlap) / max(1, min(6, len(useful_query)))
        specificity = len(overlap) / max(1, min(10, len(item_tokens)))
        return round(min(1.0, coverage * 0.7 + specificity * 0.3), 4)

    @staticmethod
    def _bundle_skill_ids(bundle: dict[str, Any]) -> list[str]:
        values = [
            *(bundle.get("skillIds") or []),
            *((bundle.get("currentVersion") or {}).get("skills") or []),
        ]
        ids = [item.get("id") if isinstance(item, dict) else item for item in values]
        return list(dict.fromkeys(str(item) for item in ids if item))

    @classmethod
    async def search(cls, query: str, skills: list[Skill]) -> dict[str, Any]:
        local_ids = {
            str((skill.manifest or {}).get("openclaw_id")): str(skill.id)
            for skill in skills
            if (skill.manifest or {}).get("openclaw_id")
        }
        if not local_ids:
            return {"boosts": {}, "paths": {}, "matched_bundles": [], "matched_specializations": []}

        bundles, specializations = await cls._catalog()
        query_tokens = _tokens(query)
        bundles_by_id = {bundle.get("id"): bundle for bundle in bundles}
        ranked_bundles = sorted(
            ((cls._relevance(query_tokens, bundle), bundle) for bundle in bundles),
            key=lambda pair: pair[0],
            reverse=True,
        )
        ranked_specs = sorted(
            ((cls._relevance(query_tokens, spec), spec) for spec in specializations),
            key=lambda pair: pair[0],
            reverse=True,
        )
        matched_bundles = [(score, item) for score, item in ranked_bundles[:8] if score >= 0.12]
        matched_specs = [(score, item) for score, item in ranked_specs[:6] if score >= 0.12]
        boosts: dict[str, float] = {}
        paths: dict[str, list[str]] = {}

        def add(openclaw_id: str, score: float, path: str) -> None:
            local_id = local_ids.get(str(openclaw_id))
            if not local_id:
                return
            boosts[local_id] = max(boosts.get(local_id, 0.0), score)
            paths.setdefault(local_id, [])
            if path not in paths[local_id]:
                paths[local_id].append(path)

        for score, bundle in matched_bundles:
            label = bundle.get("name") or bundle.get("title") or bundle.get("id")
            for skill_id in cls._bundle_skill_ids(bundle):
                add(skill_id, min(1.0, 0.55 + score * 0.45), f"bundle: {label}")

        for score, spec in matched_specs:
            label = spec.get("name") or spec.get("title") or spec.get("id")
            skill_ids = list(spec.get("requiredSkillIds") or [])
            bundle_ids: list[str] = []
            for requirement in spec.get("requirements") or []:
                skill_ids.extend(requirement.get("skillIds") or [])
                bundle_ids.extend(requirement.get("bundleIds") or [])
                if requirement.get("bundleId"):
                    bundle_ids.append(requirement["bundleId"])
            for bundle_id in bundle_ids:
                skill_ids.extend(cls._bundle_skill_ids(bundles_by_id.get(bundle_id, {})))
            for skill_id in dict.fromkeys(skill_ids):
                add(skill_id, min(1.0, 0.60 + score * 0.40), f"specialization: {label}")

        return {
            "boosts": boosts,
            "paths": paths,
            "matched_bundles": [item.get("name") or item.get("title") for _, item in matched_bundles],
            "matched_specializations": [item.get("name") or item.get("title") for _, item in matched_specs],
        }


class SkillCompatibilityService:
    @staticmethod
    def blocked_reason(skill: Skill, request: SkillActivationRequest) -> str | None:
        status = (skill.status or "available").lower()
        if status in {"disabled", "archived", "quarantined", "error"}:
            return f"status:{status}"
        if status == "deprecated" and not settings.active_skill_allow_deprecated:
            return "deprecated"
        exam = (skill.exam_status or "untested").lower()
        if exam in {"failed", "expired"} and not settings.active_skill_allow_failed_exams:
            return f"exam:{exam}"
        if settings.active_skill_require_exam_pass and exam != "passed":
            return f"exam:{exam}"
        current_rank = POSTURE_RANK.get(request.posture.lower(), 1)
        minimum_rank = POSTURE_RANK.get((skill.minimum_posture or "guarded").lower(), 1)
        if current_rank < minimum_rank:
            return f"posture_requires:{skill.minimum_posture}"
        risk = RISK_RANK.get((skill.risk_tier or "low").lower(), 0)
        if risk > POSTURE_RISK_CEILING[current_rank]:
            return f"risk:{skill.risk_tier}"
        required = set(skill.requires_tools or [])
        available = set(request.available_tools or [])
        missing = sorted(required - available)
        if missing:
            return "missing_tools:" + ",".join(missing)
        if any(tool.startswith("ide.") for tool in required) and not request.ide_enabled:
            return "ide_mode_disabled"
        task = f"{request.objective} {request.context}".lower()
        for phrase in skill.avoid_when or []:
            if str(phrase).lower() in task:
                return f"avoid_when:{phrase}"
        return None


class SkillRankingService:
    @staticmethod
    def score(
        skill: Skill,
        request: SkillActivationRequest,
        semantic: float,
        hierarchy: float = 0.0,
        hierarchy_paths: list[str] | None = None,
    ) -> tuple[float, str]:
        text = f"{request.objective} {request.context}".lower()
        task_tokens = _tokens(text)
        tags = [str(item).lower() for item in skill.tags or []]
        triggers = [str(item).lower() for item in skill.triggers or []]
        uses = [str(item).lower() for item in skill.use_when or []]
        skill_tokens = _tokens(" ".join([skill.name, *tags, *triggers, *uses]))
        overlap = len(task_tokens & skill_tokens) / max(1, min(8, len(skill_tokens)))
        phrase_hits = [phrase for phrase in [*triggers, *uses, *tags] if phrase and phrase in text]
        trigger_score = min(1.0, len(phrase_hits) * 0.35 + overlap)
        exam_score = 1.0 if skill.exam_status == "passed" else 0.0
        success_rate = skill.success_count / max(1, skill.success_count + skill.failure_count)
        priority = max(0.0, min(1.0, (skill.priority or 0) / 100.0))
        recency = 0.0
        if skill.last_used_at:
            last_used_at = skill.last_used_at
            if last_used_at.tzinfo is None:
                last_used_at = last_used_at.replace(tzinfo=timezone.utc)
            age = max(0.0, (datetime.now(timezone.utc) - last_used_at).total_seconds())
            recency = max(0.0, 1.0 - age / (30 * 86400))
        explicit = skill.id in set(request.explicit_skill_ids)
        score = (
            semantic * 0.30
            + hierarchy * 0.20
            + trigger_score * 0.20
            + exam_score * 0.15
            + success_rate * 0.10
            + recency * 0.05
            + priority * 0.05
        )
        if explicit:
            score = 1.0
        reason = (
            "explicitly requested"
            if explicit
            else (
                f"matched {'; '.join((hierarchy_paths or [])[:2])}"
                if hierarchy_paths
                else (f"matched {', '.join(phrase_hits[:3])}" if phrase_hits else f"task relevance {score:.2f}")
            )
        )
        return round(min(1.0, score), 4), reason


class SkillConflictResolver:
    @staticmethod
    def resolve(ranked: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        selected: list[dict[str, Any]] = []
        groups: dict[str, dict[str, Any]] = {}
        notes: list[str] = []
        for candidate in ranked:
            group = candidate["skill"].conflict_group
            if not group:
                selected.append(candidate)
                continue
            if group not in groups:
                groups[group] = candidate
                selected.append(candidate)
            else:
                notes.append(
                    f"{candidate['skill'].name} suppressed by {groups[group]['skill'].name} in conflict group {group}"
                )
        return selected, notes


class SkillActivationService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _emit(self, event_type: str, action: str, detail: dict[str, Any], result: str = "success") -> None:
        try:
            async with self.session.begin_nested():
                await EventLogger.emit(
                    category="skill",
                    event_type=event_type,
                    action=action,
                    result=result,
                    detail=detail,
                    db_session=self.session,
                )
        except Exception as exc:
            logger.debug("Skill audit event unavailable: %s", exc)

    async def _tables_available(self) -> bool:
        connection = await self.session.connection()
        return await connection.run_sync(
            lambda sync: all(sa_inspect(sync).has_table(name) for name in ("skills", "active_skill_runs"))
        )

    async def _installed_skills(self) -> list[Skill]:
        installed = select(SkillInstallation.skill_id).where(SkillInstallation.status == "installed")
        result = await self.session.execute(
            select(Skill).where(
                Skill.is_deleted.is_(False),
                or_(
                    Skill.id.in_(installed),
                    Skill.status == "installed",
                    Skill.exam_status == "passed",
                ),
            )
        )
        return list(result.scalars().all())

    async def _archive_content(self, skills: list[Skill]) -> dict[str, str]:
        """Load canonical instructions from the Archives Skills layer."""
        if not skills:
            return {}
        skill_ids = [skill.id for skill in skills]
        result = await self.session.execute(
            select(MemoryRecord).where(
                MemoryRecord.source_ref_id.in_(skill_ids),
                MemoryRecord.memory_type.in_(("skills", "skill")),
                MemoryRecord.is_archived.is_(False),
            )
        )
        records = list(result.scalars().all())
        # A global skill may be mirrored into multiple agent-scoped Archives.
        # Their canonical content is identical; prefer the newest populated row.
        records.sort(
            key=lambda record: record.updated_at or record.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        content: dict[str, str] = {}
        for record in records:
            if record.source_ref_id and record.content:
                content.setdefault(str(record.source_ref_id), record.content)
        return content

    async def activate(self, request: SkillActivationRequest) -> dict[str, Any]:
        run_id = request.run_id or str(uuid.uuid4())
        if (
            not settings.active_skill_usage_enabled
            or not settings.active_skill_auto_activate
            or not await self._tables_available()
        ):
            return {
                "run_id": run_id,
                "context_block": "",
                "total_injected_tokens": 0,
                "active_skills": [],
                "considered_skills": [],
                "blocked_skills": [],
                "conflict_notes": [],
                "retrieval": {
                    "strategy": "disabled",
                    "matched_bundles": [],
                    "matched_specializations": [],
                    "hierarchy_candidate_count": 0,
                    "direct_candidate_count": 0,
                },
            }
        await self._emit(
            "skill.activation.started",
            "Active skill selection started",
            {
                "run_id": run_id,
                "stack_run_id": str(request.stack_run_id) if request.stack_run_id else None,
                "posture": request.posture,
                "usage_location": request.usage_location,
            },
        )
        skills = await self._installed_skills()
        archive_content = await self._archive_content(skills)
        for skill in skills:
            SkillMetadataService.normalize(skill)
            if not skill.brief_text:
                skill.brief_text = SkillContextComposer.default_brief(skill)
        # Archives is the canonical skill-memory layer. Search it for every new
        # task, including legacy/achieved skills that predate direct embedding
        # IDs on the Skill row. Metadata ranking remains the offline fallback.
        retrieval_query = f"{request.objective}\n{request.context}"
        if skills:
            semantic, hierarchy = await asyncio.gather(
                SkillEmbeddingService.search(retrieval_query, limit=max(20, min(100, len(skills)))),
                SkillHierarchyService.search(retrieval_query, skills),
            )
        else:
            semantic, hierarchy = {}, {"boosts": {}, "paths": {}}
        ranked: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for skill in skills:
            score, reason = SkillRankingService.score(
                skill,
                request,
                semantic.get(str(skill.id), 0.0),
                hierarchy.get("boosts", {}).get(str(skill.id), 0.0),
                hierarchy.get("paths", {}).get(str(skill.id), []),
            )
            candidate = {
                "skill": skill,
                "score": score,
                "reason": reason,
                "archive_content": archive_content.get(str(skill.id)),
            }
            blocked_reason = SkillCompatibilityService.blocked_reason(skill, request)
            if blocked_reason:
                candidate["blocked_reason"] = blocked_reason
                blocked.append(candidate)
                await self._emit(
                    "skill.blocked",
                    f"Skill '{skill.name}' blocked",
                    {
                        "run_id": run_id,
                        "skill_id": str(skill.id),
                        "blocked_reason": blocked_reason,
                        "relevance_score": score,
                        "posture": request.posture,
                    },
                    result="blocked",
                )
            else:
                ranked.append(candidate)
        ranked.sort(key=lambda item: (item["score"], item["skill"].priority), reverse=True)
        eligible = [item for item in ranked if item["score"] >= 0.15]
        eligible, conflict_notes = SkillConflictResolver.resolve(eligible)
        maximum = request.max_skills or (
            settings.active_skill_max_per_step if request.step_run_id else settings.active_skill_max_per_run
        )
        selected = eligible[:maximum]
        context_block, total_tokens = SkillContextComposer.compose(
            selected, settings.active_skill_max_total_context_tokens, skills
        )
        from shogun.services.skill_trajectory_service import SkillTrajectoryService

        trajectory_service = SkillTrajectoryService(self.session)
        await trajectory_service.log_candidates(
            request=request,
            run_id=run_id,
            candidates=ranked,
            selected=selected,
            blocked=blocked,
            conflict_notes=conflict_notes,
        )
        active_items: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        for candidate in selected:
            skill = candidate["skill"]
            record = ActiveSkillRun(
                run_id=run_id,
                stack_run_id=request.stack_run_id,
                step_run_id=request.step_run_id,
                skill_id=skill.id,
                activation_reason=candidate["reason"],
                relevance_score=candidate["score"],
                activation_mode=skill.activation_mode,
                usage_location=request.usage_location,
                injected_tokens=candidate["injected_tokens"],
                posture=request.posture,
                conflict_notes=conflict_notes,
            )
            self.session.add(record)
            await self.session.flush()
            skill.last_used_at = now
            skill.usage_count = (skill.usage_count or 0) + 1
            episode_data = await trajectory_service.start_episode(
                active_run=record,
                skill=skill,
                request=request,
                selection_reason=candidate["reason"],
                retrieval_score=candidate["score"],
                brief=candidate["brief"],
            )
            episode, trajectory = episode_data if episode_data else (None, None)
            active_items.append(
                {
                    "active_skill_run_id": record.id,
                    "skill_id": skill.id,
                    "name": skill.name,
                    "skill_type": skill.skill_type,
                    "relevance_score": candidate["score"],
                    "activation_reason": candidate["reason"],
                    "activation_mode": skill.activation_mode,
                    "brief": candidate["brief"],
                    "injected_tokens": candidate["injected_tokens"],
                    "verification_checklist": skill.verification_checklist or [],
                    "model_hint": skill.model_hint,
                    "skill_episode_id": episode.id if episode else None,
                    "trajectory_id": trajectory.id if trajectory else None,
                }
            )
            await self._emit(
                "skill.activated",
                f"Skill '{skill.name}' activated",
                {
                    "run_id": run_id,
                    "stack_run_id": str(request.stack_run_id) if request.stack_run_id else None,
                    "step_run_id": str(request.step_run_id) if request.step_run_id else None,
                    "skill_id": str(skill.id),
                    "posture": request.posture,
                    "activation_reason": candidate["reason"],
                    "relevance_score": candidate["score"],
                    "injected_tokens": candidate["injected_tokens"],
                    "usage_location": request.usage_location,
                },
            )
        if context_block:
            await self._emit(
                "skill.context.injected",
                "Active skill context injected",
                {
                    "run_id": run_id,
                    "skill_ids": [str(item["skill_id"]) for item in active_items],
                    "token_count": total_tokens,
                    "usage_location": request.usage_location,
                },
            )
        if conflict_notes:
            await self._emit(
                "skill.conflict_resolved",
                "Skill conflicts resolved",
                {
                    "run_id": run_id,
                    "notes": conflict_notes,
                },
            )
        considered = [
            {
                "skill_id": item["skill"].id,
                "name": item["skill"].name,
                "relevance_score": item["score"],
                "reason": item["reason"],
                "blocked_reason": None,
            }
            for item in ranked
            if item not in selected
        ]
        blocked_items = [
            {
                "skill_id": item["skill"].id,
                "name": item["skill"].name,
                "relevance_score": item["score"],
                "reason": item["reason"],
                "blocked_reason": item["blocked_reason"],
            }
            for item in blocked
        ]
        return {
            "run_id": run_id,
            "context_block": context_block,
            "total_injected_tokens": total_tokens,
            "active_skills": active_items,
            "considered_skills": considered,
            "blocked_skills": blocked_items,
            "conflict_notes": conflict_notes,
            "retrieval": {
                "strategy": "hybrid_hierarchical_direct",
                "matched_bundles": hierarchy.get("matched_bundles", []),
                "matched_specializations": hierarchy.get("matched_specializations", []),
                "hierarchy_candidate_count": len(hierarchy.get("boosts", {})),
                "direct_candidate_count": len(semantic),
            },
        }

    async def outcome(self, record_id: uuid.UUID, outcome: str, summary: str | None = None) -> ActiveSkillRun:
        if outcome not in OUTCOMES:
            raise ValueError(f"Unsupported skill outcome: {outcome}")
        record = await self.session.get(ActiveSkillRun, record_id)
        if not record:
            raise LookupError("Active skill run not found")
        previous = record.outcome
        record.outcome = outcome
        record.outcome_summary = summary
        skill = await self.session.get(Skill, record.skill_id)
        if skill and previous in {"unknown", "not_used"}:
            if outcome in {"success", "partial"}:
                skill.success_count = (skill.success_count or 0) + 1
            elif outcome == "failed":
                skill.failure_count = (skill.failure_count or 0) + 1
        await self._emit(
            "skill.outcome.recorded",
            f"Skill outcome recorded: {outcome}",
            {
                "active_skill_run_id": str(record.id),
                "run_id": record.run_id,
                "skill_id": str(record.skill_id),
                "outcome": outcome,
                "summary": summary,
            },
        )
        from shogun.services.skill_trajectory_service import SkillTrajectoryService

        await SkillTrajectoryService(self.session).finalize_active_run(record, outcome, summary)
        return record

    async def rebuild_brief(self, skill: Skill) -> str:
        if not skill.body_text and skill.local_path:
            try:
                skill.body_text = Path(skill.local_path).read_text(encoding="utf-8")
            except OSError:
                pass
        skill.brief_text = SkillContextComposer.default_brief(skill)
        await self._emit(
            "skill.brief.rebuilt",
            f"Skill brief rebuilt for '{skill.name}'",
            {
                "skill_id": str(skill.id),
                "token_count": _estimate_tokens(skill.brief_text),
            },
        )
        return skill.brief_text

    async def ensure_defaults(self) -> None:
        defaults = [
            (
                "build-paper-writer",
                "Build Paper Writer",
                "instruction",
                ["build paper", "implementation spec", "architecture"],
                ["build paper", "implementation", "acceptance criteria"],
                [
                    "Confirm purpose, scope, non-goals, architecture, data model, APIs, UI, tests, acceptance criteria, and build order."
                ],
                "Produce complete implementation papers for coding agents.",
            ),
            (
                "shogun-architecture",
                "Shogun Architecture",
                "instruction",
                ["shogun", "architecture", "afm"],
                ["shogun", "agent flow", "flow stack"],
                ["Use existing Shogun services, posture controls, and EventLogger."],
                "Preserve Shogun terminology, governance, and architecture conventions.",
            ),
            (
                "coding-campaign",
                "Coding Campaign",
                "tool",
                ["code", "feature", "repository"],
                ["build", "implement", "fix bug"],
                ["Inspect before editing; patch safely; run focused tests; verify the build."],
                "Execute governed software changes through inspect, patch, test, and verify.",
            ),
            (
                "test-failure-analysis",
                "Test Failure Analysis",
                "verification",
                ["test", "failure", "debug"],
                ["tests fail", "failing test", "regression"],
                ["Identify the first causal failure, reproduce it, patch the cause, and rerun focused tests."],
                "Diagnose test failures from evidence instead of symptoms.",
            ),
            (
                "output-self-verification",
                "Output Self-Verification",
                "verification",
                ["verify", "review", "quality"],
                ["verify", "final review", "complete"],
                ["Check requested outcomes, evidence, permissions, and unresolved failures before completion."],
                "Check work against the task and active skill checklists before declaring completion.",
            ),
        ]
        for slug, name, skill_type, tags, triggers, checklist, description in defaults:
            existing = await self.session.execute(select(Skill).where(Skill.slug == slug))
            skill = existing.scalar_one_or_none()
            values = {
                "name": name,
                "version": "1.0.0",
                "skill_type": skill_type,
                "manifest": {"source": "built_in", "description": description},
                "status": "installed",
                "exam_status": "passed",
                "tags": tags,
                "triggers": triggers,
                "use_when": triggers,
                "minimum_posture": "campaign" if slug == "coding-campaign" else "guarded",
                "risk_tier": "medium" if slug == "coding-campaign" else "low",
                "priority": 80,
                "requires_tools": ["ide.file.read", "ide.file.apply_patch", "ide.task.run"]
                if slug == "coding-campaign"
                else [],
                "max_context_tokens": 600,
                "activation_mode": "tool_gated" if slug == "coding-campaign" else "advisory",
                "verification_checklist": checklist,
            }
            if skill is None:
                skill = Skill(slug=slug, **values)
            else:
                for key, value in values.items():
                    setattr(skill, key, value)
            skill.brief_text = SkillContextComposer.default_brief(skill)
            self.session.add(skill)
        await self.session.flush()


# Named facades keep the build-paper service boundaries explicit while sharing one deterministic core.
SkillRegistryService = SkillActivationService
SkillRetrievalService = SkillActivationService
SkillOutcomeService = SkillActivationService
SkillAuditService = SkillActivationService
