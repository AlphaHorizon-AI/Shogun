"""Governed, provider-agnostic task-aware model selection."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from shogun.config import settings
from shogun.db.models.model_definition import ModelDefinition
from shogun.db.models.model_provider import ModelProvider
from shogun.db.models.model_router import ModelRegistryEntry, ModelRoutingDecision, ModelUsageEvent
from shogun.db.models.model_routing import ModelRoutingProfile
from shogun.schemas.model_router import ModelRouteRequest, ModelUsageCreate


class NoEligibleModelError(ValueError):
    pass


DEFAULT_PROFILES = {
    "ultra_economy": {
        "name": "Ultra Economy",
        "description": "Lowest cost; strongly prefers local and cheap models.",
        "prefer_local": True,
        "quality_bias": 0,
        "cost_weight": 5,
        "latency_weight": 2,
        "max_cost_tier": 2,
    },
    "economy": {
        "name": "Economy",
        "description": "Low-cost daily work with practical escalation.",
        "prefer_local": False,
        "quality_bias": 0,
        "cost_weight": 4,
        "latency_weight": 2,
        "max_cost_tier": 3,
    },
    "balanced": {
        "name": "Balanced",
        "description": "Recommended balance of cost, speed, and quality.",
        "prefer_local": False,
        "quality_bias": 1,
        "cost_weight": 2,
        "latency_weight": 2,
        "max_cost_tier": 5,
    },
    "high_capability": {
        "name": "High Capability",
        "description": "Uses stronger models earlier for complex work.",
        "prefer_local": False,
        "quality_bias": 2,
        "cost_weight": 1,
        "latency_weight": 1,
        "max_cost_tier": 5,
    },
    "premium": {
        "name": "Premium",
        "description": "Maximum configured quality with visible cost controls.",
        "prefer_local": False,
        "quality_bias": 3,
        "cost_weight": 0,
        "latency_weight": 0,
        "max_cost_tier": 5,
    },
}

SIMPLE_TYPES = {"simple_chat", "classification", "extraction", "memory_write", "memory_retrieval"}
MODERATE_TYPES = {"summarization", "productivity_task", "browser_task", "skill_selection", "context_compaction"}
COMPLEX_TYPES = {"planning", "coding_plan", "coding_edit", "stack_planning", "stack_step_execution"}
CRITICAL_TYPES = {
    "complex_reasoning",
    "test_failure_analysis",
    "self_verification",
    "final_review",
    "visual_self_verification",
}
VISION_TYPES = {
    "visual_understanding",
    "screenshot_analysis",
    "ui_mockup_analysis",
    "photo_understanding",
    "visual_self_verification",
}

GENERIC_PROVIDER_MODEL_IDS = {
    "anthropic",
    "custom",
    "gemini",
    "google",
    "lmstudio",
    "local",
    "ollama",
    "openai",
    "openrouter",
    "provider",
}


def is_concrete_model_id(model_id: str | None, provider_type: str = "") -> bool:
    """Reject provider labels that legacy records sometimes stored as model IDs."""
    normalized = re.sub(r"[^a-z0-9]+", "", str(model_id or "").strip().lower())
    provider_label = re.sub(r"[^a-z0-9]+", "", str(provider_type or "").strip().lower())
    if not normalized:
        return False
    generic = {re.sub(r"[^a-z0-9]+", "", value) for value in GENERIC_PROVIDER_MODEL_IDS}
    return normalized not in generic and normalized != provider_label


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _setup_path() -> Path:
    return Path(settings.config_path) / "setup.json"


def read_routing_config() -> dict[str, Any]:
    defaults = {
        "enabled": True,
        "active_profile": "balanced",
        "default_profile": "balanced",
        "prefer_glm_daily_drivers": True,
        "allow_auto_escalation": True,
        "allow_auto_deescalation": True,
        "max_escalation_level": 2,
        "require_user_approval_for_premium": False,
        "daily_budget": {"enabled": False, "amount": 0, "currency": "USD", "on_exceed": "warn"},
        "profiles": {
            key: {k: v for k, v in value.items() if k not in {"name", "description"}}
            for key, value in DEFAULT_PROFILES.items()
        },
    }
    path = _setup_path()
    try:
        setup = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        setup = {}
    configured = setup.get("model_routing") or {}
    return {
        **defaults,
        **configured,
        "daily_budget": {**defaults["daily_budget"], **(configured.get("daily_budget") or {})},
        "profiles": {**defaults["profiles"], **(configured.get("profiles") or {})},
    }


def write_routing_config(config: dict[str, Any]) -> None:
    path = _setup_path()
    try:
        setup = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError):
        setup = {}
    setup["model_routing"] = config
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(setup, indent=2), encoding="utf-8")
    temporary.replace(path)


def infer_capabilities(model_id: str, provider_type: str = "") -> dict[str, bool]:
    name = model_id.lower().replace("_", "-")
    vision = any(
        token in name
        for token in (
            "gemma3",
            "llava",
            "bakllava",
            "minicpm-v",
            "moondream",
            "qwen-vl",
            "qwen2-vl",
            "qwen2.5-vl",
            "qwen3-vl",
            "pixtral",
            "vision",
            "gemini",
            "gpt-4o",
            "gpt-4.1",
            "gpt-5",
            "claude-3",
            "claude-sonnet",
        )
    )
    coding = any(token in name for token in ("coder", "code", "deepseek", "qwen", "glm", "gpt", "claude", "gemini"))
    reasoning = coding or any(token in name for token in ("reason", "r1", "opus", "sonnet", "nemotron"))
    tool_use = provider_type in {"openai", "openrouter", "anthropic", "google", "ollama", "lmstudio", "custom"}
    long_context = any(
        token in name for token in ("gemini", "claude", "gpt-4", "gpt-5", "qwen", "glm", "llama3.1", "gemma4")
    )
    return {
        "chat": True,
        "reasoning": reasoning,
        "coding": coding,
        "vision": vision,
        "tool_use": tool_use,
        "long_context": long_context,
        "json_mode": tool_use,
    }


def infer_tiers(model_id: str, local: bool) -> tuple[int, int, int]:
    name = model_id.lower()
    quality = 3
    if any(token in name for token in ("flash", "mini", "nano", "3b", "4b", "7b", "8b")):
        quality = 2
    if "glm-5" in name:
        quality = 4
    elif any(token in name for token in ("opus", "gpt-5", "70b", "72b", "80b", "405b", "pro")):
        quality = 5
    elif any(token in name for token in ("sonnet", "gpt-4", "32b", "34b", "gemini-3", "gemma4")):
        quality = 4
    cost = 1 if local else (3 if "glm-5" in name else 5 if quality == 5 else max(1, quality - 1))
    latency = 4 if local and quality >= 4 else (1 if "flash" in name else max(1, quality - 1))
    return quality, cost, latency


@dataclass(slots=True)
class RoutingResult:
    decision: ModelRoutingDecision | None
    selected: ModelRegistryEntry
    fallbacks: list[ModelRegistryEntry]
    payload: dict[str, Any]


class TaskClassifierService:
    @staticmethod
    def classify(request: ModelRouteRequest) -> str:
        if request.task_type and request.task_type != "*":
            return request.task_type
        text = request.prompt.lower()
        if any(word in text for word in ("image", "screenshot", "photo", "what do you see")):
            return "visual_understanding"
        if any(word in text for word in ("test failed", "traceback", "failing test", "debug")):
            return "test_failure_analysis"
        if any(word in text for word in ("refactor", "edit code", "implement", "patch", "write code")):
            return "coding_edit"
        if any(word in text for word in ("plan", "architecture", "design")):
            return "planning"
        if any(word in text for word in ("summarize", "summary", "condense")):
            return "summarization"
        if any(word in text for word in ("extract", "classify", "fields")):
            return "extraction"
        return "simple_chat"


class ComplexityScoringService:
    @staticmethod
    def score(request: ModelRouteRequest, task_type: str) -> int:
        if request.complexity_override:
            return request.complexity_override
        score = (
            1
            if task_type in SIMPLE_TYPES
            else 2
            if task_type in MODERATE_TYPES
            else 4
            if task_type in COMPLEX_TYPES
            else 5
            if task_type in CRITICAL_TYPES
            else 3
        )
        if len(request.prompt) > 8000 or request.context_size_estimate > 32000 or request.file_count > 5:
            score += 1
        if request.tool_count > 2 or request.risk_level in {"high", "critical"} or request.stack_depth > 1:
            score += 1
        if request.retry_count or request.verification_status == "failed":
            score += 1
        return max(1, min(5, score))


class ModelRegistryService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_connected(self) -> None:
        existing = list((await self.session.execute(select(ModelRegistryEntry))).scalars().all())
        keys = {(str(item.provider_id), item.model_id) for item in existing}
        providers = list((await self.session.execute(select(ModelProvider))).scalars().all())
        definitions = list((await self.session.execute(select(ModelDefinition))).scalars().all())
        by_provider: dict[uuid.UUID, list[ModelDefinition]] = {}
        for definition in definitions:
            by_provider.setdefault(definition.provider_id, []).append(definition)
        for provider in providers:
            model_names = [item.model_key for item in by_provider.get(provider.id, [])]
            if not model_names:
                configured = provider.config or {}
                model_names = [
                    *list(configured.get("models") or []),
                    configured.get("model_id"),
                    configured.get("model"),
                    provider.name,
                ]
            model_names = list(dict.fromkeys(
                str(model_id).strip()
                for model_id in model_names
                if is_concrete_model_id(model_id, provider.provider_type)
            ))
            for model_id in model_names:
                if (str(provider.id), model_id) in keys:
                    continue
                definition = next(
                    (item for item in by_provider.get(provider.id, []) if item.model_key == model_id), None
                )
                caps = infer_capabilities(model_id, provider.provider_type)
                if definition:
                    caps.update(
                        {
                            "vision": definition.supports_vision,
                            "tool_use": definition.supports_tools,
                            "json_mode": definition.supports_json_mode,
                        }
                    )
                quality, cost, latency = infer_tiers(model_id, provider.is_local)
                self.session.add(
                    ModelRegistryEntry(
                        model_id=model_id,
                        display_name=definition.display_name if definition else provider.name,
                        provider_id=provider.id,
                        provider=provider.provider_type,
                        connection_type="local" if provider.is_local else "api",
                        enabled=provider.status == "connected",
                        capabilities=caps,
                        quality_tier=quality,
                        cost_tier=cost,
                        latency_tier=latency,
                        context_window=(
                            definition.context_window if definition and definition.context_window else 8192
                        ),
                        local=provider.is_local,
                        role_tags=self._roles(caps, quality, provider.is_local),
                        config_json={"auto_discovered": True},
                    )
                )
        await self.session.flush()

    @staticmethod
    def _roles(caps: dict, quality: int, local: bool) -> list[str]:
        roles = ["daily_driver"]
        if quality <= 2:
            roles.append("cheap_chat")
        if caps.get("reasoning"):
            roles.append("reasoning")
        if caps.get("coding"):
            roles.append("coding")
        if caps.get("vision"):
            roles.append("vision")
        if quality >= 5:
            roles.append("premium")
        if 3 <= quality <= 4:
            roles.append("fallback")
        if local:
            roles.append("local")
        return roles

    async def list(self) -> list[ModelRegistryEntry]:
        await self.sync_connected()
        return list(
            (
                await self.session.execute(
                    select(ModelRegistryEntry).order_by(ModelRegistryEntry.provider, ModelRegistryEntry.display_name)
                )
            )
            .scalars()
            .all()
        )

    async def create(self, data: dict[str, Any]) -> ModelRegistryEntry:
        if "capabilities" in data and hasattr(data["capabilities"], "model_dump"):
            data["capabilities"] = data["capabilities"].model_dump()
        item = ModelRegistryEntry(**data)
        self.session.add(item)
        await self.session.flush()
        return item

    async def update(self, item_id: uuid.UUID, data: dict[str, Any]) -> ModelRegistryEntry | None:
        item = await self.session.get(ModelRegistryEntry, item_id)
        if not item:
            return None
        if "capabilities" in data and hasattr(data["capabilities"], "model_dump"):
            data["capabilities"] = data["capabilities"].model_dump()
        for key, value in data.items():
            setattr(item, key, value)
        await self.session.flush()
        return item

    async def delete(self, item_id: uuid.UUID) -> bool:
        result = await self.session.execute(delete(ModelRegistryEntry).where(ModelRegistryEntry.id == item_id))
        return bool(result.rowcount)


class ModelRoutingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.registry = ModelRegistryService(session)

    async def ensure_defaults(self) -> list[ModelRoutingProfile]:
        profiles = list((await self.session.execute(select(ModelRoutingProfile))).scalars().all())
        names = {_slug(item.name) for item in profiles}
        for key, config in DEFAULT_PROFILES.items():
            if key not in names:
                item = ModelRoutingProfile(
                    name=config["name"], description=config["description"], rules=[], is_default=False
                )
                self.session.add(item)
                profiles.append(item)
        # Keep the ORM default marker aligned with the persisted router setting. This
        # also upgrades installations whose legacy "Balanced (Default)" profile was
        # selected before the governed five-profile router existed.
        wanted = _slug(read_routing_config().get("active_profile") or "balanced")
        active = next((item for item in profiles if _slug(item.name) == wanted), None)
        if active and (not active.is_default or any(item.is_default for item in profiles if item is not active)):
            for item in profiles:
                item.is_default = item is active
        await self.session.flush()
        return profiles

    async def active_profile(self, override: str | None = None) -> ModelRoutingProfile:
        profiles = await self.ensure_defaults()
        config = read_routing_config()
        wanted = _slug(override or config.get("active_profile") or "balanced")
        profile = next(
            (item for item in profiles if str(item.id) == (override or "") or _slug(item.name) == wanted), None
        )
        if not profile:
            profile = next((item for item in profiles if item.is_default), None) or profiles[0]
        return profile

    async def set_active(self, profile: ModelRoutingProfile) -> None:
        await self.session.execute(update(ModelRoutingProfile).values(is_default=False))
        profile.is_default = True
        config = read_routing_config()
        config["active_profile"] = _slug(profile.name)
        write_routing_config(config)
        await self.session.flush()
        await self._audit(
            "model.routing.profile_changed",
            f"Active model routing profile changed to {profile.name}",
            detail={"profile_id": str(profile.id), "profile": _slug(profile.name)},
            db_session=self.session,
        )

    async def route(self, request: ModelRouteRequest, *, persist: bool = True) -> RoutingResult:
        profile = await self.active_profile(request.profile_override)
        profile_key = _slug(profile.name)
        config = read_routing_config()
        if (
            profile_key == "premium"
            and config.get("require_user_approval_for_premium")
            and not request.metadata.get("premium_approved")
        ):
            raise NoEligibleModelError("Premium routing requires user approval under the active cost policy.")
        budget = config.get("daily_budget") or {}
        budget_used = 0.0
        budget_exceeded = False
        if budget.get("enabled") and float(budget.get("amount") or 0) > 0:
            day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            budget_used = float(
                (
                    await self.session.scalar(
                        select(func.sum(ModelUsageEvent.estimated_cost)).where(
                            ModelUsageEvent.created_at >= day_start,
                        )
                    )
                )
                or 0
            )
            budget_exceeded = budget_used >= float(budget["amount"])
            if budget_exceeded and budget.get("on_exceed") == "block":
                await self._audit(
                    "model.routing.blocked_budget",
                    "Daily model budget has been reached",
                    result="failure",
                    detail={"used": budget_used, "budget": float(budget["amount"])},
                    db_session=self.session,
                )
                raise NoEligibleModelError(
                    f"Daily model budget reached ({budget_used:.2f} / {float(budget['amount']):.2f} "
                    f"{budget.get('currency', 'USD')})."
                )
        task_type = TaskClassifierService.classify(request)
        complexity = ComplexityScoringService.score(request, task_type)
        requirements = set(request.required_capabilities)
        if task_type in VISION_TYPES:
            requirements.add("vision")
        # Raw image bytes are not equivalent to text tokens. Vision providers
        # tokenize images independently, so file size must not force a
        # long-context model and exclude otherwise compatible local vision.
        if request.context_size_estimate > 32000 and task_type not in VISION_TYPES:
            requirements.add("long_context")
        candidates = [
            item
            for item in await self.registry.list()
            if item.enabled
            and item.model_id not in request.exclude_model_ids
            and is_concrete_model_id(item.model_id, item.provider)
        ]
        providers = {item.id: item for item in (await self.session.execute(select(ModelProvider))).scalars().all()}
        candidates = [
            item
            for item in candidates
            if item.provider_id and item.provider_id in providers and providers[item.provider_id].status == "connected"
        ]
        if request.local_only:
            candidates = [item for item in candidates if item.local]
        candidates = [
            item
            for item in candidates
            if all((item.capabilities or {}).get(capability, False) for capability in requirements)
        ]
        if not candidates:
            required = ", ".join(sorted(requirements)) or "connected chat model"
            await self._audit(
                "model.routing.no_eligible_model",
                "No eligible model found",
                result="failure",
                detail={"required_capabilities": sorted(requirements), "task_type": task_type},
                db_session=self.session,
            )
            raise NoEligibleModelError(f"No eligible model found for this task. Required capabilities: {required}.")
        profile_config = {
            **DEFAULT_PROFILES.get(profile_key, DEFAULT_PROFILES["balanced"]),
            **(config.get("profiles", {}).get(profile_key) or {}),
        }
        max_cost = int(profile_config.get("max_cost_tier", 5))
        if budget_exceeded and budget.get("on_exceed") == "downgrade":
            max_cost = min(max_cost, 2)
        within_budget = [item for item in candidates if item.cost_tier <= max_cost]
        if within_budget:
            candidates = within_budget
        elif budget_exceeded and budget.get("on_exceed") == "downgrade":
            await self._audit(
                "model.routing.blocked_budget",
                "No eligible lower-cost model is available after the daily budget was reached",
                result="failure",
                detail={"used": budget_used, "budget": float(budget["amount"])},
                db_session=self.session,
            )
            raise NoEligibleModelError("Daily budget reached and no eligible lower-cost model is available.")
        preferred_ids = self._legacy_preference(profile, task_type)
        ranked = sorted(
            candidates,
            key=lambda item: self._rank(item, complexity, task_type, request, profile_config, config, preferred_ids),
            reverse=True,
        )
        selected, fallbacks = ranked[0], ranked[1:3]
        reason = self._reason(selected, profile.name, task_type, complexity, requirements, request.escalation_level)
        payload = {
            "run_id": request.run_id,
            "stack_run_id": request.stack_run_id,
            "step_id": request.step_id,
            "task_type": task_type,
            "complexity_score": complexity,
            "active_profile": profile_key,
            "selected_registry_id": selected.id,
            "selected_model": selected.model_id,
            "selected_provider": selected.provider,
            "fallback_model": fallbacks[0].model_id if fallbacks else None,
            "fallback_provider": fallbacks[0].provider if fallbacks else None,
            "reason": reason,
            "estimated_cost_tier": selected.cost_tier,
            "estimated_latency_tier": selected.latency_tier,
            "escalation_level": request.escalation_level,
            "requires_vision": "vision" in requirements,
            "requires_tool_use": "tool_use" in requirements,
            "requires_json_mode": "json_mode" in requirements,
            "candidate_count": len(ranked),
            "metadata": {
                "required_capabilities": sorted(requirements),
                "budget_warning": (
                    f"Daily budget reached: {budget_used:.2f} / {float(budget.get('amount') or 0):.2f} "
                    f"{budget.get('currency', 'USD')}. Policy: {budget.get('on_exceed', 'warn')}."
                    if budget_exceeded
                    else None
                ),
                **request.metadata,
            },
        }
        decision = None
        if persist:
            decision = ModelRoutingDecision(
                run_id=request.run_id,
                stack_run_id=request.stack_run_id,
                step_id=request.step_id,
                task_type=task_type,
                complexity_score=complexity,
                active_profile=profile_key,
                selected_registry_id=selected.id,
                selected_model=selected.model_id,
                selected_provider=selected.provider,
                fallback_model=payload["fallback_model"],
                reason=reason,
                estimated_cost_tier=selected.cost_tier,
                estimated_latency_tier=selected.latency_tier,
                escalation_level=request.escalation_level,
                requires_vision=payload["requires_vision"],
                requires_tool_use=payload["requires_tool_use"],
                requires_json_mode=payload["requires_json_mode"],
                metadata_json=payload["metadata"],
            )
            self.session.add(decision)
            await self.session.flush()
            payload["id"] = decision.id
            payload["created_at"] = decision.created_at
            audit_detail = json.loads(json.dumps(payload, default=str))
            await self._audit(
                "model.routing.escalated" if request.escalation_level else "model.routing.decision",
                reason,
                model_used=selected.model_id,
                provider_used=selected.provider,
                detail=audit_detail,
                db_session=self.session,
            )
        return RoutingResult(decision, selected, fallbacks, payload)

    @staticmethod
    def _legacy_preference(profile: ModelRoutingProfile, task_type: str) -> list[str]:
        rule = next((item for item in (profile.rules or []) if item.get("task_type") == task_type), None)
        rule = rule or next((item for item in (profile.rules or []) if item.get("task_type") == "*"), None)
        return (
            [str(value) for value in ([rule.get("primary_model_id")] + (rule.get("fallback_model_ids") or [])) if value]
            if rule
            else []
        )

    @staticmethod
    def _rank(
        item: ModelRegistryEntry,
        complexity: int,
        task_type: str,
        request: ModelRouteRequest,
        profile: dict,
        config: dict,
        preferred_ids: list[str],
    ) -> float:
        target = min(5, max(1, complexity + int(profile.get("quality_bias", 1)) - 1 + request.escalation_level))
        score = 20 - abs(item.quality_tier - target) * 4
        if item.quality_tier < min(complexity, 4):
            score -= 15
        score -= item.cost_tier * int(profile.get("cost_weight", 2))
        score -= item.latency_tier * int(profile.get("latency_weight", 2))
        if profile.get("prefer_local") and item.local:
            score += 12
        if config.get("prefer_glm_daily_drivers") and "glm" in item.model_id.lower() and not request.local_only:
            score += 15
        if task_type.startswith("coding") or task_type == "test_failure_analysis":
            score += 8 if (item.capabilities or {}).get("coding") else 0
        if task_type in {"final_review", "self_verification", "visual_self_verification"}:
            score += item.quality_tier * 2
        identifiers = {str(item.id), str(item.provider_id), item.model_id}
        for index, preferred in enumerate(preferred_ids):
            if preferred in identifiers:
                score += 50 - index * 5
        return score

    @staticmethod
    def _reason(
        item: ModelRegistryEntry, profile: str, task_type: str, complexity: int, requirements: set[str], escalation: int
    ) -> str:
        detail = f"{task_type}, complexity {complexity}"
        if requirements:
            detail += f", requires {', '.join(sorted(requirements))}"
        if escalation:
            detail += f", escalation level {escalation}"
        return f"{profile} selected {item.display_name} as the cheapest sufficient eligible model for {detail}."

    async def decisions(self, run_id: uuid.UUID | None = None, stack_run_id: uuid.UUID | None = None, limit: int = 100):
        query = select(ModelRoutingDecision)
        if run_id:
            query = query.where(ModelRoutingDecision.run_id == run_id)
        if stack_run_id:
            query = query.where(ModelRoutingDecision.stack_run_id == stack_run_id)
        return list(
            (await self.session.execute(query.order_by(ModelRoutingDecision.created_at.desc()).limit(limit)))
            .scalars()
            .all()
        )

    @staticmethod
    async def _audit(event_type: str, action: str, result: str = "success", **kwargs: Any) -> None:
        try:
            from shogun.services.event_logger import EventLogger

            await EventLogger.emit(category="model", event_type=event_type, action=action, result=result, **kwargs)
        except Exception:
            pass


class ModelUsageLogger:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, body: ModelUsageCreate) -> ModelUsageEvent:
        item = ModelUsageEvent(**body.model_dump())
        self.session.add(item)
        await self.session.flush()
        await ModelRoutingService._audit(
            "model.usage.logged" if body.success else "model.usage.error",
            f"Model usage recorded for {body.model_id}",
            result="success" if body.success else "failure",
            model_used=body.model_id,
            provider_used=body.provider,
            duration_ms=body.latency_ms,
            db_session=self.session,
        )
        return item

    async def list(self, stack_run_id: uuid.UUID | None = None, limit: int = 200) -> list[ModelUsageEvent]:
        query = select(ModelUsageEvent)
        if stack_run_id:
            query = query.where(ModelUsageEvent.stack_run_id == stack_run_id)
        return list(
            (await self.session.execute(query.order_by(ModelUsageEvent.created_at.desc()).limit(limit))).scalars().all()
        )

    async def summary(self) -> dict[str, Any]:
        row = (
            await self.session.execute(
                select(
                    func.count(ModelUsageEvent.id),
                    func.sum(ModelUsageEvent.input_tokens),
                    func.sum(ModelUsageEvent.output_tokens),
                    func.sum(ModelUsageEvent.estimated_cost),
                    func.avg(ModelUsageEvent.latency_ms),
                )
            )
        ).one()
        return {
            "events": row[0] or 0,
            "input_tokens": row[1] or 0,
            "output_tokens": row[2] or 0,
            "estimated_cost": float(row[3] or 0),
            "average_latency_ms": int(row[4] or 0),
        }
