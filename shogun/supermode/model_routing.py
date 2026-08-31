"""Description-guided routing-profile selection for Supermode tasks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from shogun.db.models.model_routing import ModelRoutingProfile
from shogun.services.model_router import (
    COMPLEX_TYPES,
    CRITICAL_TYPES,
    MODERATE_TYPES,
    SIMPLE_TYPES,
    ModelRoutingService,
    automatic_profile_key,
    read_routing_config,
)

_GENERIC_TERMS = {
    "and",
    "agent",
    "are",
    "but",
    "not",
    "of",
    "or",
    "from",
    "configured",
    "fleet",
    "for",
    "into",
    "operator",
    "logic",
    "mission",
    "model",
    "models",
    "profile",
    "routing",
    "shogun",
    "specialist",
    "task",
    "tasks",
    "that",
    "the",
    "this",
    "use",
    "uses",
    "with",
    "work",
    "workstream",
}


def _normalized_token(value: str) -> str:
    token = value.lower()
    if token.endswith("ies") and len(token) > 5:
        return f"{token[:-3]}y"
    if token.endswith("s") and not token.endswith("ss") and len(token) > 4:
        return token[:-1]
    return token


def _tokens(*values: Any) -> set[str]:
    return {
        normalized
        for value in values
        for token in re.findall(r"[a-z0-9][a-z0-9_+-]{2,}", str(value or "").lower())
        if (normalized := _normalized_token(token)) not in _GENERIC_TERMS
    }


def _description_fit(query_tokens: set[str], profile: ModelRoutingProfile) -> tuple[float, tuple[str, ...]]:
    profile_tokens = _tokens(profile.name, profile.description)
    overlap = tuple(sorted(query_tokens & profile_tokens))
    if not overlap:
        return 0.0, ()
    breadth = min(1.0, len(overlap) / 2)
    specificity = len(overlap) / max(1, min(8, len(profile_tokens)))
    return min(1.0, breadth * 0.65 + specificity * 0.35), overlap


def _configured_for_task(profile: ModelRoutingProfile, task_type: str) -> bool:
    if automatic_profile_key(profile.name):
        return True
    for rule in profile.rules or []:
        if rule.get("task_type") in {task_type, "*"} and rule.get("primary_model_id"):
            return True
    return False


def _strategy_fit(profile: ModelRoutingProfile, task_type: str, query_tokens: set[str]) -> float:
    strategy = automatic_profile_key(profile.name)
    if not strategy:
        return 0.0

    if task_type in CRITICAL_TYPES:
        scores = {"high_capability": 0.86, "balanced": 0.55, "economy": 0.22, "ultra_economy": 0.08}
    elif task_type in COMPLEX_TYPES:
        scores = {"high_capability": 0.74, "balanced": 0.64, "economy": 0.32, "ultra_economy": 0.12}
    elif task_type in MODERATE_TYPES:
        scores = {"balanced": 0.72, "economy": 0.54, "high_capability": 0.42, "ultra_economy": 0.30}
    elif task_type in SIMPLE_TYPES:
        scores = {"economy": 0.76, "ultra_economy": 0.66, "balanced": 0.55, "high_capability": 0.24}
    else:
        scores = {"balanced": 0.65, "high_capability": 0.48, "economy": 0.45, "ultra_economy": 0.24}

    score = scores.get(strategy, 0.0)
    economy_terms = {"budget", "cheap", "cost", "economical", "economy", "efficient", "local", "offline"}
    quality_terms = {"best", "critical", "maximum", "premium", "quality", "rigorous", "strongest"}
    if query_tokens & economy_terms:
        if strategy == "ultra_economy":
            score += 0.28
        elif strategy == "economy":
            score += 0.18
    if query_tokens & quality_terms:
        if strategy == "high_capability":
            score += 0.22
        elif strategy == "premium":
            score = max(score, 0.92)
    # Premium is never selected merely because a task is difficult. The task
    # or profile description must explicitly ask for premium/maximum quality.
    if strategy == "premium" and not query_tokens & quality_terms:
        return 0.0
    return min(1.0, score)


@dataclass(frozen=True, slots=True)
class SupermodeRoutingChoice:
    profile_id: str
    profile_name: str
    profile_description: str
    source: str
    reason: str
    score: float
    matched_terms: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "profile_description": self.profile_description,
            "source": self.source,
            "reason": self.reason,
            "score": self.score,
            "matched_terms": list(self.matched_terms),
        }


async def rank_supermode_routing_profiles(
    session: AsyncSession,
    *,
    mission: Any,
    task: Any,
    agent: Any | None,
) -> list[SupermodeRoutingChoice]:
    """Rank usable Katana profiles for one task and retain safe fallbacks."""
    service = ModelRoutingService(session)
    profiles = await service.ensure_defaults()
    active = await service.active_profile()
    assigned_id = str((getattr(agent, "routing_preferences", None) or {}).get("model_routing_profile_id") or "")
    task_type = str(getattr(task, "task_type", None) or "simple_chat")
    query_tokens = _tokens(
        getattr(task, "title", ""),
        getattr(task, "objective", ""),
        getattr(task, "instructions", ""),
        task_type,
        *(getattr(task, "required_capabilities", None) or []),
        *(getattr(task, "required_tools", None) or []),
        getattr(agent, "role_name", "") if agent else "",
        getattr(agent, "role_description", "") if agent else "",
        getattr(agent, "objective", "") if agent else "",
    )
    config = read_routing_config()
    premium_requires_approval = bool(config.get("require_user_approval_for_premium"))
    ranked: list[tuple[float, str, SupermodeRoutingChoice]] = []

    for profile in profiles:
        if not _configured_for_task(profile, task_type):
            continue
        strategy = automatic_profile_key(profile.name)
        if strategy == "premium" and premium_requires_approval:
            continue

        description_fit, matched_terms = _description_fit(query_tokens, profile)
        strategy_fit = _strategy_fit(profile, task_type, query_tokens)
        is_assigned = str(profile.id) == assigned_id
        is_active = str(profile.id) == str(active.id)

        if strategy:
            score = strategy_fit * 0.82 + description_fit * 0.18
        elif description_fit:
            # A named profile description is explicit operator guidance, so a
            # real text match should outrank a generic automatic strategy.
            score = 0.45 + description_fit * 0.45
        else:
            score = 0.0
        if is_assigned:
            # A Samurai assignment is explicit operator intent. It remains the
            # normal choice unless another profile has a strong task-specific
            # description match.
            score = max(score, 0.64)
        score = min(1.0, score)

        if is_assigned:
            source = "samurai_preference"
            reason = f"{profile.name} is the routing profile assigned to {getattr(agent, 'role_name', 'this Samurai')}."
        elif matched_terms and not strategy:
            source = "description_match"
            reason = (
                f"{profile.name} matched this task through its description "
                f"({', '.join(matched_terms[:5])})."
            )
        elif strategy_fit:
            source = "task_strategy"
            reason = f"{profile.name} fits the {task_type.replace('_', ' ')} task strategy."
        elif is_active:
            source = "active_profile"
            reason = f"{profile.name} is the active Katana routing profile."
        else:
            source = "fallback"
            reason = f"{profile.name} is an available fallback routing profile."

        ranked.append(
            (
                score,
                profile.name.casefold(),
                SupermodeRoutingChoice(
                    profile_id=str(profile.id),
                    profile_name=profile.name,
                    profile_description=str(profile.description or ""),
                    source=source,
                    reason=reason,
                    score=round(score, 4),
                    matched_terms=matched_terms,
                ),
            )
        )

    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    by_id = {choice.profile_id: choice for _, _, choice in ranked}
    preferred = [ranked[0][2]] if ranked and ranked[0][0] >= 0.25 else []
    fallbacks: list[SupermodeRoutingChoice] = []
    for profile_id in (assigned_id, str(active.id)):
        if profile_id and profile_id in by_id:
            fallbacks.append(by_id[profile_id])
    balanced = next(
        (choice for _, _, choice in ranked if automatic_profile_key(choice.profile_name) == "balanced"),
        None,
    )
    if balanced:
        fallbacks.append(balanced)

    ordered: list[SupermodeRoutingChoice] = []
    for choice in [*preferred, *fallbacks]:
        if choice.profile_id not in {item.profile_id for item in ordered}:
            ordered.append(choice)
    if not ordered and ranked:
        ordered.append(ranked[0][2])
    return ordered
