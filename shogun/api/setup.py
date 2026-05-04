"""Setup API — First-run wizard endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

from shogun.config import settings, PROJECT_ROOT
from shogun.db.engine import async_session_factory
from shogun.schemas.common import ApiResponse

router = APIRouter(prefix="/setup", tags=["Setup"])

SETUP_JSON = Path(settings.config_path) / "setup.json"
CONSTITUTION_PATH = Path(settings.config_path) / "constitution.yaml"
MANDATE_PATH = Path(settings.config_path) / "mandate.md"


def _read_setup() -> dict:
    """Read the setup.json config, or return defaults."""
    if SETUP_JSON.exists():
        try:
            return json.loads(SETUP_JSON.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"language": "en", "setup_complete": False}


def _write_setup(data: dict) -> None:
    """Write setup.json config."""
    SETUP_JSON.parent.mkdir(parents=True, exist_ok=True)
    SETUP_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")


@router.get("/status", response_model=ApiResponse)
async def get_setup_status():
    """Return whether setup has been completed, plus path info."""
    setup = _read_setup()
    return ApiResponse(
        data={
        "setup_complete": setup.get("setup_complete", False),
            "language": setup.get("language", "en"),
            "operator_name": setup.get("operator_name", "Daimyo"),
            "data_path": setup.get("data_path", str(PROJECT_ROOT / "data")),
            "config_path": str(settings.config_path),
        }
    )


@router.post("/reset", response_model=ApiResponse)
async def reset_setup():
    """Reset setup state so the wizard triggers again on next visit to /."""
    setup = _read_setup()
    setup["setup_complete"] = False
    _write_setup(setup)
    return ApiResponse(data={"message": "Setup reset. The wizard will trigger on next visit."})


class ProviderSetup(BaseModel):
    provider_type: str
    name: str
    auth_type: str = "api_key"
    api_key: str | None = None
    base_url: str | None = None
    models: list[str] = Field(default_factory=list)


class SetupCompletePayload(BaseModel):
    language: str = "en"
    operator_name: str = "Daimyo"
    data_path: str = ""
    agent_name: str = "Shogun Prime"
    description: str = "Master orchestrator of the Samurai Network."
    persona_id: str | None = None
    autonomy: int = 50
    tone: str = "analytical"
    risk_tolerance: str = "medium"
    verbosity: str = "medium"
    planning_depth: str = "medium"
    tool_usage_style: str = "balanced"
    security_bias: str = "balanced"
    memory_style: str = "focused"
    behavioral_directives: str | None = None
    providers: list[ProviderSetup] = Field(default_factory=list)
    constitution: str | None = None
    mandate: str | None = None
    primary_model: str = ""
    fallback_models: list[str] = Field(default_factory=list)


@router.post("/complete", response_model=ApiResponse)
async def complete_setup(payload: SetupCompletePayload):
    """Process the full wizard payload — creates everything in one go."""
    from shogun.db.models.agent import Agent
    from shogun.db.models.model_provider import ModelProvider
    from sqlalchemy import select

    created_provider_ids: list[str] = []
    # Map frontend-generated provider UUIDs → actual DB UUIDs so model
    # selections (primary_model / fallback_models) reference real records.
    frontend_to_db_id: dict[str, str] = {}

    async with async_session_factory() as session:
        from shogun.db.models.operator import Operator
        # ── 0. Create/update Operator ────────────────────────────────
        op_result = await session.execute(select(Operator).limit(1))
        op = op_result.scalar_one_or_none()
        if op:
            op.display_name = payload.operator_name
        else:
            op = Operator(username="admin", display_name=payload.operator_name, role="owner", preferences={})
            session.add(op)

        # ── 1. Create model providers ────────────────────────────────
        for idx, prov in enumerate(payload.providers):
            slug = f"{prov.provider_type}-{prov.name}".lower().replace(" ", "-")
            # Check if provider with this slug already exists
            existing = await session.execute(
                select(ModelProvider).where(ModelProvider.slug == slug)
            )
            existing_record = existing.scalar_one_or_none()

            if existing_record:
                # Update existing
                existing_record.base_url = prov.base_url
                existing_record.config = {
                    "api_key": prov.api_key,
                    "models": prov.models,
                }
                existing_record.status = "connected"
                created_provider_ids.append(str(existing_record.id))
                # We don't know the frontend UUID here but we'll try to match below
            else:
                provider_record = ModelProvider(
                    provider_type=prov.provider_type,
                    name=prov.name,
                    slug=slug,
                    base_url=prov.base_url,
                    auth_type=prov.auth_type,
                    is_local=prov.provider_type in ("ollama", "lmstudio", "local"),
                    status="connected",
                    health_status="unknown",
                    config={
                        "api_key": prov.api_key,
                        "models": prov.models,
                    },
                )
                session.add(provider_record)
                await session.flush()
                created_provider_ids.append(str(provider_record.id))

        # ── 1b. Build frontend→DB provider ID mapping ────────────────
        # The frontend uses crypto.randomUUID() as provider IDs in model
        # selection values like "frontendUUID::modelName".  We need to
        # remap those to the real database UUIDs so the chat endpoint and
        # Tenshu profile can resolve providers correctly.
        #
        # Strategy: extract all unique frontend provider UUIDs from the
        # primary_model / fallback_models strings, then match them to
        # DB providers by index order (providers list is in the same
        # order as created_provider_ids).
        frontend_uuids_seen: list[str] = []
        all_model_refs = [payload.primary_model] + payload.fallback_models
        for ref in all_model_refs:
            if "::" in ref:
                fe_id = ref.split("::")[0]
                if fe_id and fe_id not in frontend_uuids_seen:
                    frontend_uuids_seen.append(fe_id)

        # Match frontend UUIDs to DB provider IDs by looking up which
        # provider has models that appear in the model references
        for fe_id in frontend_uuids_seen:
            # Find which provider index this frontend UUID belongs to
            # by checking which provider's models list contains the
            # model names referenced with this frontend UUID
            model_names_for_fe = [
                ref.split("::")[1] for ref in all_model_refs
                if ref.startswith(f"{fe_id}::")
            ]
            for idx, prov in enumerate(payload.providers):
                if idx < len(created_provider_ids):
                    # Check if any of the model names match this provider's models
                    prov_models = set(prov.models) | {prov.name}
                    if any(m in prov_models for m in model_names_for_fe):
                        frontend_to_db_id[fe_id] = created_provider_ids[idx]
                        break
            # Fallback: if we only have one provider, map directly
            if fe_id not in frontend_to_db_id and len(created_provider_ids) == 1:
                frontend_to_db_id[fe_id] = created_provider_ids[0]

        def _remap_model_ref(ref: str) -> str:
            """Replace frontend UUID prefix with real DB UUID."""
            if "::" not in ref:
                return ref
            fe_id, model_name = ref.split("::", 1)
            db_id = frontend_to_db_id.get(fe_id, fe_id)
            return f"{db_id}::{model_name}"

        remapped_primary = _remap_model_ref(payload.primary_model)
        remapped_fallbacks = [_remap_model_ref(fb) for fb in payload.fallback_models]

        # ── 2. Create/update Shogun agent ────────────────────────────
        result = await session.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary == True,
                Agent.is_deleted == False,
            )
        )
        shogun = result.scalar_one_or_none()

        bushido_settings = {
            "nightly_consolidation": True,
            "weekly_performance_audit": True,
            "skill_health_check": True,
            "persona_drift_check": False,
            "primary_model": remapped_primary,
            "fallback_models": remapped_fallbacks,
        }

        if shogun:
            shogun.name = payload.agent_name
            shogun.description = payload.description
            shogun.status = "active"
            if payload.persona_id:
                shogun.persona_id = uuid.UUID(payload.persona_id)
            shogun.bushido_settings = bushido_settings
        else:
            shogun = Agent(
                agent_type="shogun",
                name=payload.agent_name,
                slug="primary-shogun",
                description=payload.description,
                status="active",
                is_primary=True,
                spawn_policy="manual",
                bushido_settings=bushido_settings,
            )
            if payload.persona_id:
                shogun.persona_id = uuid.UUID(payload.persona_id)
            session.add(shogun)

        await session.commit()

    # ── 3. Write constitution ────────────────────────────────────
    if payload.constitution:
        CONSTITUTION_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONSTITUTION_PATH.write_text(payload.constitution, encoding="utf-8")

    # ── 4. Write mandate ─────────────────────────────────────────
    if payload.mandate:
        MANDATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        MANDATE_PATH.write_text(payload.mandate, encoding="utf-8")

    # ── 5. Create data directory if custom path specified ────────
    if payload.data_path:
        data_dir = Path(payload.data_path)
        data_dir.mkdir(parents=True, exist_ok=True)

    # ── 6. Mark setup as complete ────────────────────────────────
    setup_data = {
        "setup_complete": True,
        "language": payload.language,
        "operator_name": payload.operator_name,
        "data_path": payload.data_path or str(PROJECT_ROOT / "data"),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "agent_name": payload.agent_name,
        "providers_created": len(created_provider_ids),
    }
    _write_setup(setup_data)

    return ApiResponse(
        data={
            "message": "The Shogun has risen.",
            "setup_complete": True,
            "providers_created": created_provider_ids,
        }
    )
