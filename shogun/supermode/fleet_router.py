"""Skill-aware selection of durable fleet Samurai for Supermode workstreams."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.agent import Agent
from shogun.db.models.samurai_profile import SamuraiProfile
from shogun.db.models.skill import Skill
from shogun.db.models.supermode import MissionAgent
from shogun.services.agent_service import AgentService

_GENERIC_WORDS = {
    "agent",
    "analysis",
    "mission",
    "process",
    "specialist",
    "task",
    "work",
    "workstream",
}


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_+-]{2,}", value.lower())
        if token not in _GENERIC_WORDS
    }


def _overlap_score(query: set[str], candidate: set[str]) -> float:
    if not query or not candidate:
        return 0.0
    overlap = query & candidate
    if not overlap:
        return 0.0
    coverage = len(overlap) / max(1, min(8, len(query)))
    specificity = len(overlap) / max(1, min(8, len(candidate)))
    return min(1.0, coverage * 0.65 + specificity * 0.35)


def _skill_text(skill: Skill) -> str:
    return " ".join(
        [
            skill.name,
            skill.description,
            *(str(value) for value in skill.tags or []),
            *(str(value) for value in skill.triggers or []),
            *(str(value) for value in skill.use_when or []),
        ]
    )


@dataclass(frozen=True, slots=True)
class FleetMatch:
    agent: Agent
    profile: SamuraiProfile
    skills: tuple[Skill, ...]
    matched_skills: tuple[str, ...]
    score: float
    reason: str


@dataclass(slots=True)
class _FleetCandidate:
    agent: Agent
    profile: SamuraiProfile
    skills: tuple[Skill, ...]
    active_assignments: int
    reserved_assignments: int = 0

    @property
    def has_capacity(self) -> bool:
        return self.active_assignments + self.reserved_assignments < self.profile.max_parallel_jobs


class FleetSamuraiRouter:
    """Load the fleet once, then reserve suitable Samurai deterministically."""

    def __init__(self, candidates: list[_FleetCandidate]):
        self.candidates = candidates

    @classmethod
    async def load(cls, session: AsyncSession) -> FleetSamuraiRouter:
        agents = list(
            (
                await session.scalars(
                    select(Agent).where(
                        Agent.agent_type == "samurai",
                        Agent.status.in_(["active", "idle", "running"]),
                        Agent.is_deleted.is_(False),
                    )
                )
            ).all()
        )
        profiles = {
            profile.agent_id: profile
            for profile in (
                await session.scalars(
                    select(SamuraiProfile).where(
                        SamuraiProfile.agent_id.in_([agent.id for agent in agents])
                    )
                )
            ).all()
        } if agents else {}
        skills = {str(skill.id): skill for skill in await AgentService(session).get_assignable_skills()}
        active_counts = {
            fleet_agent_id: int(count)
            for fleet_agent_id, count in (
                await session.execute(
                    select(MissionAgent.fleet_agent_id, func.count(MissionAgent.id))
                    .where(
                        MissionAgent.source_type == "fleet",
                        MissionAgent.fleet_agent_id.is_not(None),
                        MissionAgent.status.in_(["planned", "starting", "active", "waiting", "blocked"]),
                    )
                    .group_by(MissionAgent.fleet_agent_id)
                )
            ).all()
        }
        candidates: list[_FleetCandidate] = []
        for agent in agents:
            profile = profiles.get(agent.id)
            if not profile:
                continue
            assigned = tuple(
                skills[skill_id]
                for skill_id in dict.fromkeys(str(value) for value in profile.assigned_skill_ids or [])
                if skill_id in skills
            )
            candidates.append(
                _FleetCandidate(
                    agent=agent,
                    profile=profile,
                    skills=assigned,
                    active_assignments=active_counts.get(agent.id, 0),
                )
            )
        return cls(candidates)

    def route(
        self,
        *,
        role_name: str,
        role_description: str,
        objective: str,
        task_type: str,
        required_tools: list[str],
        excluded_agent_ids: set[uuid.UUID] | None = None,
    ) -> FleetMatch | None:
        query_text = " ".join([role_name, role_description, objective, task_type, *required_tools])
        query_tokens = _tokens(query_text)
        excluded = excluded_agent_ids or set()
        ranked: list[tuple[float, str, _FleetCandidate, tuple[str, ...]]] = []

        for candidate in self.candidates:
            if candidate.agent.id in excluded or not candidate.has_capacity:
                continue
            profile = candidate.profile
            allowed = {str(value).lower() for value in profile.allowed_task_types or []}
            blocked = {str(value).lower() for value in profile.blocked_task_types or []}
            if task_type.lower() in blocked or (allowed and task_type.lower() not in allowed):
                continue

            role_text = " ".join(
                [
                    candidate.agent.name,
                    candidate.agent.description or "",
                    *(str(value) for value in candidate.agent.tags or []),
                    profile.role,
                    *(str(value) for value in profile.specializations or []),
                    getattr(profile.samurai_role, "name", "") or "",
                    getattr(profile.samurai_role, "purpose", "") or "",
                    getattr(profile.samurai_role, "description", "") or "",
                ]
            )
            profile_score = _overlap_score(query_tokens, _tokens(role_text))
            exact_role = role_name.lower() in role_text.lower() or profile.role.lower() in role_name.lower()
            if exact_role:
                profile_score = max(profile_score, 0.85)

            skill_scores = [
                (_overlap_score(query_tokens, _tokens(_skill_text(skill))), skill)
                for skill in candidate.skills
            ]
            matched_skills = tuple(
                skill.name for score, skill in sorted(skill_scores, key=lambda item: item[0], reverse=True)
                if score >= 0.12
            )
            skill_score = max((score for score, _ in skill_scores), default=0.0)
            task_type_bonus = 0.15 if task_type.lower() in allowed else 0.0
            availability = 1.0 - (
                (candidate.active_assignments + candidate.reserved_assignments)
                / max(1, profile.max_parallel_jobs)
            )
            score = min(1.0, profile_score * 0.50 + skill_score * 0.38 + task_type_bonus + availability * 0.07)
            if score < 0.18:
                continue

            ranked.append((score, candidate.agent.name.lower(), candidate, matched_skills))

        if not ranked:
            return None
        score, _, selected, matched_skills = max(ranked, key=lambda item: (item[0], item[1]))
        selected.reserved_assignments += 1
        return FleetMatch(
            agent=selected.agent,
            profile=selected.profile,
            skills=selected.skills,
            matched_skills=matched_skills,
            score=round(score, 4),
            reason="; ".join(
                [
                    *(
                        ["matched assigned skills " + ", ".join(matched_skills[:3])]
                        if matched_skills
                        else []
                    ),
                    (
                        f"matched fleet role {selected.profile.role}"
                        if role_name.lower() in (selected.profile.role or "").lower()
                        or (selected.profile.role or "").lower() in role_name.lower()
                        else "matched role and specialization metadata"
                    ),
                    f"route score {score:.2f}",
                ]
            ),
        )
