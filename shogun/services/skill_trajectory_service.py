"""Order 10 skill trajectory capture, conservative scoring, redaction, and export."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import uuid
import zipfile
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.active_skill_run import ActiveSkillRun
from shogun.db.models.skill import Skill
from shogun.db.models.skill_trajectory import (
    SkillCandidateRetrieval,
    SkillEpisode,
    SkillImprovementCandidate,
    SkillOutcomeScore,
    SkillToolLink,
    SkillTrajectory,
    SkillVerificationLink,
)
from shogun.services.event_logger import EventLogger

logger = logging.getLogger(__name__)
SCHEMA_VERSION = "1.0"


class SkillTrajectoryRedactor:
    """Keep secrets and raw environment values out of structured evidence."""

    PATTERNS = (
        re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*[^\s,;]+"),
        re.compile(r"\b(sk-[A-Za-z0-9_-]{8,}|ghp_[A-Za-z0-9]{8,})\b"),
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    )

    @classmethod
    def text(cls, value: Any, limit: int = 2000) -> str:
        result = str(value or "")
        for pattern in cls.PATTERNS:
            result = pattern.sub("[REDACTED]", result)
        lines = []
        for line in result.splitlines():
            if re.match(r"^\s*[A-Z][A-Z0-9_]{2,}\s*=", line):
                lines.append("[REDACTED ENV VALUE]")
            else:
                lines.append(line)
        return "\n".join(lines)[:limit]

    @classmethod
    def value(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                str(key): "[REDACTED]" if re.search(r"(?i)(key|secret|token|password)", str(key)) else cls.value(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls.value(item) for item in value[:100]]
        return cls.text(value) if isinstance(value, str) else value


class SkillContributionEvaluator:
    @staticmethod
    def evaluate(outcome: str, verifications: list[SkillVerificationLink], tool_count: int) -> dict[str, Any]:
        normalized = {"partial": "partial_success", "failed": "failure", "not_used": "unknown"}.get(outcome, outcome)
        passed = any(item.status in {"passed", "success", "completed"} for item in verifications)
        failed = any(item.status in {"failed", "failure", "error"} for item in verifications)
        if normalized == "blocked":
            contribution, confidence = "blocked", 1.0
        elif normalized == "success" and passed:
            contribution, confidence = "clearly_positive", 0.95
        elif normalized == "success":
            contribution, confidence = "likely_positive", 0.7
        elif normalized == "partial_success":
            contribution, confidence = "likely_positive", 0.65
        elif normalized == "failure" and failed and tool_count:
            contribution, confidence = "likely_negative", 0.7
        elif normalized == "failure":
            contribution, confidence = "unclear", 0.5
        else:
            contribution, confidence = "not_used", 0.8
        explanation = (
            f"Contribution classified as {contribution} from final outcome {normalized}, "
            f"{len(verifications)} verification result(s), and {tool_count} linked tool call(s)."
        )
        return {"outcome": normalized, "classification": contribution, "confidence": confidence, "explanation": explanation}


class SkillOutcomeScorer:
    @staticmethod
    def score(evaluation: dict[str, Any], verifications: list[SkillVerificationLink]) -> tuple[float, str]:
        outcome = evaluation["outcome"]
        passed = any(item.status in {"passed", "success", "completed"} for item in verifications)
        failed = any(item.status in {"failed", "failure", "error"} for item in verifications)
        if outcome == "success":
            value = 1.0 if passed else 0.75
        elif outcome == "partial_success":
            value = 0.5
        elif outcome == "failure":
            value = -0.25 if failed else 0.0
        else:
            value = 0.0
        return value, f"Deterministic conservative score {value:.2f}: {evaluation['explanation']}"


class SkillTrajectoryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def tables_available(self) -> bool:
        connection = await self.session.connection()
        names = ("skill_candidate_retrievals", "skill_episodes", "skill_trajectories")
        return await connection.run_sync(lambda sync: all(sa_inspect(sync).has_table(name) for name in names))

    async def _emit(self, event_type: str, action: str, detail: dict[str, Any], result: str = "success") -> None:
        try:
            async with self.session.begin_nested():
                await EventLogger.emit(
                    category="skill", event_type=event_type, action=action, result=result,
                    detail=SkillTrajectoryRedactor.value(detail), db_session=self.session,
                )
        except Exception as exc:
            logger.debug("Skill trajectory audit event unavailable: %s", exc)

    async def log_candidates(
        self, *, request: Any, run_id: str, candidates: list[dict], selected: list[dict],
        blocked: list[dict], conflict_notes: list[str],
    ) -> SkillCandidateRetrieval | None:
        if not await self.tables_available():
            return None
        candidate_ids = [str(item["skill"].id) for item in candidates + blocked]
        selected_ids = [str(item["skill"].id) for item in selected]
        rejected_ids = [skill_id for skill_id in candidate_ids if skill_id not in selected_ids]
        scores = {str(item["skill"].id): item["score"] for item in candidates + blocked}
        record = SkillCandidateRetrieval(
            run_id=run_id, stack_run_id=request.stack_run_id, step_run_id=request.step_run_id,
            flow_id=getattr(request, "flow_id", None), node_id=getattr(request, "node_id", None),
            agent_id=getattr(request, "agent_id", None),
            query_text=SkillTrajectoryRedactor.text(request.objective, 1000),
            task_summary=SkillTrajectoryRedactor.text(request.objective, 500),
            candidate_skill_ids=candidate_ids, retrieval_scores=scores,
            selected_skill_ids=selected_ids, rejected_skill_ids=rejected_ids,
            metadata_json={"usage_location": request.usage_location, "posture": request.posture,
                           "conflict_notes": conflict_notes},
        )
        self.session.add(record)
        await self.session.flush()
        await self._emit("skill.candidates.retrieved", "Skill candidates retrieved", {
            "retrieval_id": str(record.id), "run_id": run_id, "stack_run_id": str(request.stack_run_id) if request.stack_run_id else None,
            "candidate_skill_ids": candidate_ids, "selected_skill_ids": selected_ids,
            "rejected_skill_ids": rejected_ids, "posture": request.posture,
        })
        for skill_id in rejected_ids:
            await self._emit("skill.rejected", "Skill candidate rejected", {
                "retrieval_id": str(record.id), "run_id": run_id, "skill_id": skill_id,
                "relevance_score": scores.get(skill_id), "posture": request.posture,
            }, result="rejected")
        if conflict_notes:
            await self._emit("skill.conflict.detected", "Skill conflict detected and resolved", {
                "run_id": run_id, "conflicts": conflict_notes, "resolution": "highest ranked candidate retained",
            })
        return record

    async def start_episode(
        self, *, active_run: ActiveSkillRun, skill: Skill, request: Any,
        selection_reason: str, retrieval_score: float, brief: str,
    ) -> tuple[SkillEpisode, SkillTrajectory] | None:
        if not await self.tables_available():
            return None
        now = datetime.now(timezone.utc)
        episode = SkillEpisode(
            active_skill_run_id=active_run.id, skill_id=skill.id, skill_version=skill.version,
            run_id=active_run.run_id, stack_run_id=active_run.stack_run_id, step_run_id=active_run.step_run_id,
            flow_id=getattr(request, "flow_id", None), node_id=getattr(request, "node_id", None),
            agent_id=getattr(request, "agent_id", None), model_id=getattr(request, "model_id", None),
            model_profile=getattr(request, "model_profile", None), posture=active_run.posture,
            task_summary=SkillTrajectoryRedactor.text(request.objective, 1000), selection_reason=selection_reason,
            injection_mode="context_block", status="injected", started_at=now,
            metadata_json={"usage_location": active_run.usage_location, "injected_tokens": active_run.injected_tokens},
        )
        self.session.add(episode)
        await self.session.flush()
        content_hash = skill.hash or hashlib.sha256((brief or "").encode("utf-8")).hexdigest()
        trajectory = SkillTrajectory(
            skill_episode_id=episode.id, skill_id=skill.id, skill_version=skill.version,
            run_id=episode.run_id, stack_run_id=episode.stack_run_id, step_run_id=episode.step_run_id,
            final_outcome="unknown", contribution="unclear", score=0.0,
            trajectory_json={
                "schema_version": SCHEMA_VERSION, "trajectory_id": None,
                "skill": {"skill_id": str(skill.id), "name": skill.name, "version": skill.version, "content_hash": content_hash},
                "execution_context": {
                    "run_id": episode.run_id, "stack_run_id": str(episode.stack_run_id) if episode.stack_run_id else None,
                    "step_run_id": str(episode.step_run_id) if episode.step_run_id else None,
                    "flow_id": episode.flow_id, "node_id": episode.node_id, "agent_id": episode.agent_id,
                    "posture": episode.posture, "model_id": episode.model_id, "model_profile": episode.model_profile,
                },
                "task": {"task_summary": episode.task_summary, "success_criteria": []},
                "skill_selection": {
                    "selection_reason": selection_reason, "retrieval_score": retrieval_score,
                    "selected_by": "active_skill_usage", "injected": True, "injection_mode": "context_block",
                },
                "events": [{"type": "skill.injected", "timestamp": now.isoformat(),
                            "summary": "Compact skill brief injected into execution context."}],
                "verification": {"required": bool(skill.verification_checklist), "checks": [], "final_verification_status": "unknown"},
                "outcome": {"status": "unknown", "score": 0.0, "skill_contribution": "unclear", "explanation": "Episode active."},
                "improvement_notes": [],
            },
            metadata_json={"redacted": True, "raw_prompt_stored": False},
        )
        self.session.add(trajectory)
        await self.session.flush()
        payload = dict(trajectory.trajectory_json)
        payload["trajectory_id"] = str(trajectory.id)
        trajectory.trajectory_json = payload
        common = {
            "run_id": episode.run_id, "stack_run_id": str(episode.stack_run_id) if episode.stack_run_id else None,
            "step_run_id": str(episode.step_run_id) if episode.step_run_id else None,
            "flow_id": episode.flow_id, "node_id": episode.node_id, "agent_id": episode.agent_id,
            "model_id": episode.model_id, "skill_id": str(skill.id), "skill_version": skill.version,
            "posture": episode.posture, "episode_id": str(episode.id), "trajectory_id": str(trajectory.id),
        }
        await self._emit("skill.selected", f"Skill '{skill.name}' selected", {**common, "selection_reason": selection_reason, "retrieval_score": retrieval_score})
        await self._emit("skill.injected", f"Skill '{skill.name}' injected", {**common, "content_hash": content_hash, "injection_mode": "context_block"})
        await self._emit("skill.trajectory.created", f"Trajectory created for '{skill.name}'", common)
        return episode, trajectory

    async def _episodes_for_active_runs(self, active_run_ids: list[str | uuid.UUID]) -> list[SkillEpisode]:
        ids = []
        for value in active_run_ids:
            try:
                ids.append(uuid.UUID(str(value)))
            except ValueError:
                continue
        if not ids or not await self.tables_available():
            return []
        return list((await self.session.execute(select(SkillEpisode).where(SkillEpisode.active_skill_run_id.in_(ids)))).scalars().all())

    async def _append_event(self, episode: SkillEpisode, event_type: str, summary: str, detail: dict | None = None) -> None:
        trajectory = (await self.session.execute(select(SkillTrajectory).where(SkillTrajectory.skill_episode_id == episode.id))).scalar_one_or_none()
        if not trajectory:
            return
        payload = dict(trajectory.trajectory_json or {})
        events = list(payload.get("events") or [])
        events.append({"type": event_type, "timestamp": datetime.now(timezone.utc).isoformat(),
                       "summary": SkillTrajectoryRedactor.text(summary, 500),
                       "detail": SkillTrajectoryRedactor.value(detail or {})})
        payload["events"] = events[-200:]
        trajectory.trajectory_json = payload

    async def link_tool_call(
        self, active_run_ids: list[str | uuid.UUID], *, tool_call_id: str | None,
        tool_name: str, tool_input: Any, tool_output: Any, status: str = "completed",
    ) -> int:
        episodes = await self._episodes_for_active_runs(active_run_ids)
        for episode in episodes:
            link = SkillToolLink(
                skill_episode_id=episode.id, tool_call_id=tool_call_id, tool_name=tool_name,
                tool_input_summary=SkillTrajectoryRedactor.text(json.dumps(SkillTrajectoryRedactor.value(tool_input), default=str), 1000),
                tool_output_summary=SkillTrajectoryRedactor.text(tool_output, 1500), status=status,
                metadata_json={"full_output_stored": False},
            )
            self.session.add(link)
            await self.session.flush()
            await self._append_event(episode, "skill.tool_call.linked", f"Tool {tool_name} {status}.", {"tool_link_id": str(link.id)})
            await self._emit("skill.tool_call.linked", f"Tool '{tool_name}' linked to skill episode", {
                "episode_id": str(episode.id), "skill_id": str(episode.skill_id), "run_id": episode.run_id,
                "tool_call_id": tool_call_id, "tool_name": tool_name, "status": status,
            })
        return len(episodes)

    async def link_verification(
        self, active_run_ids: list[str | uuid.UUID], *, verification_id: str | None,
        verification_type: str, expected: str, observed: str, status: str, score: float,
    ) -> int:
        episodes = await self._episodes_for_active_runs(active_run_ids)
        for episode in episodes:
            link = SkillVerificationLink(
                skill_episode_id=episode.id, verification_id=verification_id,
                verification_type=verification_type, expected_result=SkillTrajectoryRedactor.text(expected, 1000),
                observed_result=SkillTrajectoryRedactor.text(observed, 1500), status=status,
                score=max(0.0, min(1.0, score)), metadata_json={},
            )
            self.session.add(link)
            await self.session.flush()
            await self._append_event(episode, "skill.verification.linked", f"Verification {status}.", {"verification_link_id": str(link.id)})
            await self._emit("skill.verification.linked", "Verification linked to skill episode", {
                "episode_id": str(episode.id), "skill_id": str(episode.skill_id), "run_id": episode.run_id,
                "verification_id": verification_id, "verification_type": verification_type, "status": status, "score": score,
            }, result=status)
        return len(episodes)

    async def link_output(
        self,
        active_run_ids: list[str | uuid.UUID],
        *,
        output_summary: Any,
        output_type: str = "model_output",
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Attach a redacted output reference without persisting the raw response."""
        episodes = await self._episodes_for_active_runs(active_run_ids)
        summary = SkillTrajectoryRedactor.text(output_summary, 1500)
        safe_metadata = SkillTrajectoryRedactor.value(metadata or {})
        for episode in episodes:
            await self._append_event(
                episode,
                "skill.output.linked",
                summary,
                {"output_type": output_type, **safe_metadata},
            )
            await self._emit(
                "skill.output.linked",
                "Redacted execution output linked to skill episode",
                {
                    "episode_id": str(episode.id),
                    "skill_id": str(episode.skill_id),
                    "skill_version": episode.skill_version,
                    "run_id": episode.run_id,
                    "stack_run_id": str(episode.stack_run_id) if episode.stack_run_id else None,
                    "flow_id": episode.flow_id,
                    "node_id": episode.node_id,
                    "agent_id": episode.agent_id,
                    "model_id": episode.model_id,
                    "posture": episode.posture,
                    "output_type": output_type,
                },
            )
        return len(episodes)

    async def finalize_active_run(self, active_run: ActiveSkillRun, outcome: str, summary: str | None) -> SkillTrajectory | None:
        episodes = await self._episodes_for_active_runs([active_run.id])
        if not episodes:
            return None
        episode = episodes[0]
        trajectory = (await self.session.execute(select(SkillTrajectory).where(SkillTrajectory.skill_episode_id == episode.id))).scalar_one()
        if trajectory.finalized_at is not None:
            return trajectory
        verifications = list((await self.session.execute(select(SkillVerificationLink).where(SkillVerificationLink.skill_episode_id == episode.id))).scalars().all())
        tools = list((await self.session.execute(select(SkillToolLink).where(SkillToolLink.skill_episode_id == episode.id))).scalars().all())
        evaluation = SkillContributionEvaluator.evaluate(outcome, verifications, len(tools))
        score, explanation = SkillOutcomeScorer.score(evaluation, verifications)
        now = datetime.now(timezone.utc)
        episode.status = "completed" if evaluation["outcome"] in {"success", "partial_success"} else evaluation["outcome"]
        episode.completed_at = now
        trajectory.final_outcome = evaluation["outcome"]
        trajectory.contribution = evaluation["classification"]
        trajectory.score = score
        trajectory.finalized_at = now
        payload = dict(trajectory.trajectory_json or {})
        payload["verification"] = {
            "required": payload.get("verification", {}).get("required", False),
            "checks": [{"type": item.verification_type, "status": item.status, "score": item.score,
                        "observed_result": item.observed_result} for item in verifications],
            "final_verification_status": verifications[-1].status if verifications else "not_recorded",
        }
        payload["outcome"] = {
            "status": evaluation["outcome"], "score": score,
            "skill_contribution": evaluation["classification"], "confidence": evaluation["confidence"],
            "explanation": explanation, "summary": SkillTrajectoryRedactor.text(summary, 1000),
        }
        trajectory.trajectory_json = payload
        self.session.add(SkillOutcomeScore(
            skill_episode_id=episode.id, skill_id=episode.skill_id, skill_version=episode.skill_version,
            run_id=episode.run_id, stack_run_id=episode.stack_run_id, score=score,
            score_type="contribution", scoring_method="deterministic_v1", explanation=explanation,
            metadata_json={"classification": evaluation["classification"], "confidence": evaluation["confidence"]},
        ))
        await self._append_event(episode, "skill.outcome.scored", explanation, {"score": score, "classification": evaluation["classification"]})
        lifecycle_type = {
            "success": "skill.used",
            "partial_success": "skill.used",
            "failure": "skill.misapplied" if evaluation["classification"] == "likely_negative" else "skill.used",
            "blocked": "skill.blocked",
            "unknown": "skill.ignored",
        }.get(evaluation["outcome"], "skill.used")
        await self._emit(lifecycle_type, f"Skill lifecycle resolved as {evaluation['outcome']}", {
            "episode_id": str(episode.id), "trajectory_id": str(trajectory.id),
            "skill_id": str(episode.skill_id), "run_id": episode.run_id,
            "outcome": evaluation["outcome"], "contribution": evaluation["classification"],
        }, result=evaluation["outcome"])
        event_type = "skill.episode.completed" if evaluation["outcome"] in {"success", "partial_success"} else "skill.episode.failed"
        await self._emit(event_type, f"Skill episode {episode.status}", {
            "episode_id": str(episode.id), "trajectory_id": str(trajectory.id), "skill_id": str(episode.skill_id),
            "skill_version": episode.skill_version, "run_id": episode.run_id,
            "stack_run_id": str(episode.stack_run_id) if episode.stack_run_id else None,
            "step_run_id": str(episode.step_run_id) if episode.step_run_id else None,
            "model_id": episode.model_id, "posture": episode.posture, "outcome": evaluation["outcome"],
        }, result=evaluation["outcome"])
        await self._emit("skill.outcome.scored", "Skill outcome scored", {
            "episode_id": str(episode.id), "trajectory_id": str(trajectory.id), "skill_id": str(episode.skill_id),
            "run_id": episode.run_id, "score": score, "classification": evaluation["classification"],
        })
        await self._emit("skill.trajectory.finalized", "Skill trajectory finalized", {
            "trajectory_id": str(trajectory.id), "episode_id": str(episode.id), "skill_id": str(episode.skill_id),
            "run_id": episode.run_id, "outcome": evaluation["outcome"], "score": score,
        })
        if score <= 0 and evaluation["outcome"] not in {"blocked", "unknown"}:
            await self.create_improvement_candidate(trajectory, summary or explanation)
        return trajectory

    async def create_improvement_candidate(self, trajectory: SkillTrajectory, observed: str) -> SkillImprovementCandidate:
        existing = (await self.session.execute(select(SkillImprovementCandidate).where(
            SkillImprovementCandidate.based_on_trajectory_id == trajectory.id
        ))).scalar_one_or_none()
        if existing:
            return existing
        candidate = SkillImprovementCandidate(
            skill_id=trajectory.skill_id, skill_version=trajectory.skill_version,
            based_on_trajectory_id=trajectory.id, issue_type="weak_or_failed_trajectory",
            observed_problem=SkillTrajectoryRedactor.text(observed, 1500),
            suggested_improvement="Review the failed trajectory and add a clearer procedure, prerequisite, or verification step.",
            validation_idea="Replay the revised skill on a held-out task with the same failure mode.",
            priority="high" if trajectory.score < 0 else "medium", status="candidate",
            metadata_json={"trajectory_score": trajectory.score, "outcome": trajectory.final_outcome},
        )
        self.session.add(candidate)
        await self.session.flush()
        payload = dict(trajectory.trajectory_json or {})
        notes = list(payload.get("improvement_notes") or [])
        notes.append({"candidate_id": str(candidate.id), "issue_type": candidate.issue_type,
                      "suggested_improvement": candidate.suggested_improvement})
        payload["improvement_notes"] = notes
        trajectory.trajectory_json = payload
        await self._emit("skill.improvement_candidate.created", "Skill improvement candidate created", {
            "candidate_id": str(candidate.id), "trajectory_id": str(trajectory.id),
            "skill_id": str(trajectory.skill_id), "priority": candidate.priority,
        })
        return candidate


class SkillTrajectoryExporter:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def export(self, trajectories: list[SkillTrajectory], format_name: str = "jsonl") -> tuple[bytes, str, str]:
        safe = [SkillTrajectoryRedactor.value(item.trajectory_json) for item in trajectories]
        if format_name == "markdown":
            chunks = []
            for item in safe:
                outcome = item.get("outcome") or {}
                chunks.append(
                    f"# {item.get('skill', {}).get('name', 'Skill trajectory')}\n\n"
                    f"- Task: {item.get('task', {}).get('task_summary', '')}\n"
                    f"- Outcome: {outcome.get('status', 'unknown')}\n"
                    f"- Score: {outcome.get('score', 0)}\n"
                    f"- Contribution: {outcome.get('skill_contribution', 'unclear')}\n\n"
                    f"```json\n{json.dumps(item, indent=2, default=str)}\n```"
                )
            return "\n\n---\n\n".join(chunks).encode(), "text/markdown", "skill-trajectories.md"
        jsonl = "\n".join(json.dumps(item, default=str, separators=(",", ":")) for item in safe).encode()
        if format_name == "zip":
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("skill-trajectories.jsonl", jsonl)
                archive.writestr("manifest.json", json.dumps({"schema_version": SCHEMA_VERSION, "count": len(safe)}))
            return buffer.getvalue(), "application/zip", "skill-trajectories.zip"
        return jsonl, "application/x-ndjson", "skill-trajectories.jsonl"
