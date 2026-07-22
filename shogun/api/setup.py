"""Setup API — First-run wizard endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field, model_validator

from shogun.config import PROJECT_ROOT, settings
from shogun.db.engine import async_session_factory
from shogun.schemas.common import ApiResponse

router = APIRouter(prefix="/setup", tags=["Setup"])

SETUP_JSON = Path(settings.config_path) / "setup.json"
CONSTITUTION_PATH = Path(settings.config_path) / "constitution.yaml"
MANDATE_PATH = Path(settings.config_path) / "mandate.md"

RONIN_DESKTOP_DEFAULTS = {
    "enabled": False,
    "minimum_posture": "ronin",
    "audit_all_actions": True,
    "require_visible_indicator": True,
    "kill_switch_enabled": True,
    "default_action_timeout_seconds": 20,
    "max_action_retries": 3,
    "dynamic_waits_enabled": True,
    "verification_required": True,
    "allow_mouse": True,
    "allow_keyboard": True,
    "allow_window_management": True,
    "allow_application_launch": True,
    "allow_file_dialogs": True,
    "allow_sensitive_apps": False,
    "high_risk_requires_approval": True,
    "critical_actions_blocked": True,
    "protected_applications": ["1Password", "Bitwarden", "KeePass", "Windows Security", "Keychain Access"],
    "blocked_keywords_in_window_titles": ["password", "bank", "payment", "security code", "two-factor", "2FA"],
}

MADO_DEFAULTS = {
    "enabled": True,
    "default_mode": "visible",
    "headless_allowed": True,
    "visible_allowed": True,
    "profiles_root": "./data/mado/profiles",
    "downloads_root": "./data/mado/downloads",
    "screenshots_root": "./data/mado/screenshots",
    "artifacts_root": "./data/mado/artifacts",
    "allowed_domains": [],
    "blocked_domains": [],
    "allow_external_urls": False,
    "allow_persistent_profiles": True,
    "allow_authenticated_sessions": False,
    "allow_file_downloads": "approval",
    "allow_file_uploads": "approval",
    "allow_form_submit": "approval",
    "require_verification": True,
    "max_pages_per_run": 50,
    "max_runtime_seconds": 1800,
    "default_navigation_timeout_ms": 30000,
    "default_action_timeout_ms": 10000,
    "retry": {"max_attempts": 3, "backoff_seconds": [1, 3, 8]},
    "page_readiness": {
        "wait_for_dom_content_loaded": True,
        "wait_for_network_idle": True,
        "network_idle_timeout_ms": 1500,
        "stability_check_enabled": True,
    },
    "dialog_policy": {
        "cookie_banner_policy": "accept_necessary_only",
        "confirm_dialog_policy": "dismiss",
        "permission_prompt_policy": "deny",
    },
    "audit": {
        "log_all_actions": True,
        "capture_screenshots_on_error": True,
        "capture_screenshots_on_verification": True,
    },
}

BENCHMARK_MODE_DEFAULTS = {
    "enabled": True,
    "output_root": "./data/benchmarks",
    "providers": {
        "ale": {
            "enabled": True,
            "default_posture": "ronin",
            "default_model_profile": "ale_balanced",
            "max_runtime_minutes": 180,
            "output_retention_days": 30,
            "trajectory_export": True,
            "artifact_export": True,
            "redact_secrets": True,
            "allow_external_network": "inherit_from_ale_task",
            "cua_mcp": {
                "enabled": True,
                "transport": "stdio",
                "connection_source": "ale_runtime",
                "tool_namespace": "cua",
            },
        }
    },
}

FILE_FORMAT_HANDLING_DEFAULTS = {
    "enabled": True,
    "detect_by_content": True,
    "safe_parsing": True,
    "max_preview_bytes": 1_048_576,
    "max_parse_bytes_default": 52_428_800,
    "max_rows_preview": 100,
    "max_json_depth": 100,
    "mask_secrets_in_preview": True,
    "archive_extraction": {
        "enabled": True,
        "requires_approval": True,
        "max_uncompressed_bytes": 524_288_000,
        "block_executables": True,
    },
    "indexing": {
        "enabled": True,
        "embed_full_large_files": False,
        "store_profiles_in_memory": True,
    },
}


def _read_setup() -> dict:
    """Read the setup.json config, or return defaults."""
    if SETUP_JSON.exists():
        try:
            setup = json.loads(SETUP_JSON.read_text(encoding="utf-8"))
            setup["ronin_desktop_control"] = {
                **RONIN_DESKTOP_DEFAULTS,
                **setup.get("ronin_desktop_control", {}),
            }
            setup["mado"] = {**MADO_DEFAULTS, **setup.get("mado", {})}
            setup["benchmark_mode"] = {
                **BENCHMARK_MODE_DEFAULTS,
                **setup.get("benchmark_mode", {}),
            }
            setup["file_format_handling"] = {
                **FILE_FORMAT_HANDLING_DEFAULTS,
                **setup.get("file_format_handling", {}),
            }
            return setup
        except Exception:
            pass
    return {
        "language": "en",
        "setup_complete": False,
        "ronin_desktop_control": dict(RONIN_DESKTOP_DEFAULTS),
        "mado": dict(MADO_DEFAULTS),
        "benchmark_mode": dict(BENCHMARK_MODE_DEFAULTS),
        "file_format_handling": dict(FILE_FORMAT_HANDLING_DEFAULTS),
    }


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
            "installation_mode": setup.get("installation_mode", "single"),
            "team_members": setup.get("team_members", []),
            "deployment_mode": settings.deployment_mode,
            "ronin_available": settings.deployment_mode == "desktop",
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


class TeamMemberSetup(BaseModel):
    display_name: str = Field(min_length=1, max_length=255)
    email: str | None = None
    is_primary: bool = False
    channel: Literal["web", "telegram", "microsoft_teams"] = "telegram"
    telegram_user_id: str | None = None
    teams_aad_object_id: str | None = None
    teams_user_principal_name: str | None = None


class SetupCompletePayload(BaseModel):
    language: str = "en"
    operator_name: str = "Daimyo"
    installation_mode: Literal["single", "team"] = "single"
    team_members: list[TeamMemberSetup] = Field(default_factory=list)
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
    routing_profile: str = "custom"
    ronin_enabled: bool = False

    @model_validator(mode="after")
    def validate_team_setup(self):
        if self.installation_mode == "single":
            return self
        if len(self.team_members) < 2:
            raise ValueError("Team mode requires a Primary Admin and at least one Team Member.")
        primary = [member for member in self.team_members if member.is_primary]
        if len(primary) != 1:
            raise ValueError("Team mode requires exactly one Primary Admin.")
        if primary[0].channel != "web":
            raise ValueError("The Primary Admin must use the web platform.")
        for member in self.team_members:
            if member.is_primary:
                continue
            if member.channel == "web":
                raise ValueError("Only the Primary Admin may use the web platform.")
            if member.channel == "telegram" and not str(member.telegram_user_id or "").strip():
                raise ValueError(f"Telegram user ID is required for {member.display_name}.")
            if member.channel == "microsoft_teams" and not (
                str(member.teams_aad_object_id or "").strip()
                or str(member.teams_user_principal_name or "").strip()
            ):
                raise ValueError(f"Teams Entra Object ID or sign-in email is required for {member.display_name}.")
        identities = [
            (
                member.channel,
                str(
                    member.telegram_user_id
                    or member.teams_aad_object_id
                    or member.teams_user_principal_name
                    or ""
                ).strip().casefold(),
            )
            for member in self.team_members
            if not member.is_primary
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("Each Team Member must have a unique Telegram or Teams identity.")
        return self


@router.post("/complete", response_model=ApiResponse)
async def complete_setup(payload: SetupCompletePayload):
    """Process the full wizard payload — creates everything in one go."""
    from sqlalchemy import select

    from shogun.db.models.agent import Agent
    from shogun.db.models.model_provider import ModelProvider

    created_provider_ids: list[str] = []
    # Map frontend-generated provider UUIDs → actual DB UUIDs so model
    # selections (primary_model / fallback_models) reference real records.
    frontend_to_db_id: dict[str, str] = {}

    async with async_session_factory() as session:
        from shogun.db.models.operator import Operator

        # ── 0. Create/update Operator ────────────────────────────────
        op_result = await session.execute(select(Operator).where(Operator.username == "admin"))
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
            existing = await session.execute(select(ModelProvider).where(ModelProvider.slug == slug))
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
            model_names_for_fe = [ref.split("::")[1] for ref in all_model_refs if ref.startswith(f"{fe_id}::")]
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

        # The routing profile is the model-selection authority.  Fresh setups
        # default to Custom so the ordered models chosen in this wizard become
        # the actual governed route rather than a disconnected legacy setting.
        from shogun.services.model_router import ModelRoutingService

        routing_service = ModelRoutingService(session)
        await routing_service.registry.sync_connected()
        routing_profiles = await routing_service.ensure_defaults()
        requested_profile = (payload.routing_profile or "custom").lower().replace(" ", "_")
        if requested_profile == "custom" and not remapped_primary:
            requested_profile = "balanced"
        selected_routing_profile = next(
            (
                profile for profile in routing_profiles
                if profile.name.lower().replace(" ", "_") == requested_profile
            ),
            next(profile for profile in routing_profiles if profile.name == "Balanced"),
        )
        if selected_routing_profile.name == "Custom":
            selected_routing_profile.rules = [{
                "task_type": "*",
                "primary_model_id": remapped_primary,
                "fallback_model_ids": remapped_fallbacks,
            }]
        await routing_service.set_active(selected_routing_profile)

        # ── 2. Create/update Shogun agent ────────────────────────────
        result = await session.execute(
            select(Agent).where(
                Agent.agent_type == "shogun",
                Agent.is_primary.is_(True),
                Agent.is_deleted.is_(False),
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
            shogun.model_routing_profile_id = selected_routing_profile.id
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
                model_routing_profile_id=selected_routing_profile.id,
            )
            if payload.persona_id:
                shogun.persona_id = uuid.UUID(payload.persona_id)
            session.add(shogun)

        await session.flush()
        from shogun.services.team_identity import configure_team_members

        persisted_members = await configure_team_members(
            session,
            installation_mode=payload.installation_mode,
            admin_name=payload.operator_name,
            members=[member.model_dump() for member in payload.team_members],
            agent_id=shogun.id,
        )
        shogun.bushido_settings = {
            **dict(shogun.bushido_settings or {}),
            "installation_mode": payload.installation_mode,
            "team_members": persisted_members,
        }

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
        "installation_mode": payload.installation_mode,
        "team_members": persisted_members,
        "data_path": payload.data_path or str(PROJECT_ROOT / "data"),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "agent_name": payload.agent_name,
        "providers_created": len(created_provider_ids),
        "ronin_enabled": payload.ronin_enabled,
    }
    _write_setup(setup_data)

    return ApiResponse(
        data={
            "message": "The Shogun has risen.",
            "setup_complete": True,
            "providers_created": created_provider_ids,
        }
    )


# ── Ronin Dependency Management ─────────────────────────────────


def _check_module(module_name: str) -> dict:
    """Check if a Python module is installed and return version info."""
    try:
        mod = __import__(module_name)
        version = getattr(mod, "__version__", getattr(mod, "VERSION", "unknown"))
        return {"installed": True, "version": str(version)}
    except ImportError:
        return {"installed": False, "version": None}


def _detect_os_info() -> dict:
    """Detect the current OS and display server."""
    import os
    import platform

    system = platform.system()
    os_name = "Windows" if system == "Windows" else "macOS" if system == "Darwin" else "Linux"

    display_server = None
    if system == "Linux":
        if os.environ.get("WAYLAND_DISPLAY"):
            display_server = "wayland"
        elif os.environ.get("DISPLAY"):
            display_server = "x11"
        else:
            display_server = "unknown"

    # OS-specific notes
    notes: list[str] = []
    if os_name == "macOS":
        notes.append("macOS requires Accessibility permissions for keyboard and mouse control.")
        notes.append("Go to: System Preferences → Privacy & Security → Accessibility")
    elif os_name == "Linux" and display_server == "x11":
        notes.append("Linux X11 requires: xdotool, python3-tk, python3-dev")
    elif os_name == "Linux" and display_server == "wayland":
        notes.append("Wayland has limited desktop control support. X11 is recommended.")
        notes.append("Consider switching to an X11 session for full Ronin functionality.")

    return {
        "os": os_name,
        "platform": platform.platform(),
        "display_server": display_server,
        "notes": notes,
    }


@router.get("/ronin-check", response_model=ApiResponse)
async def check_ronin_deps():
    """Check Ronin desktop control dependency status and OS compatibility."""
    if settings.deployment_mode == "server":
        return ApiResponse(
            data={
                "os": "Container",
                "display_server": None,
                "deps": {},
                "all_core_installed": False,
                "recommendation": "unavailable",
                "ronin_enabled_in_setup": False,
                "notes": ["Ronin host desktop control is unavailable in Shogun Server mode."],
            }
        )

    os_info = _detect_os_info()

    deps = {
        "mss": _check_module("mss"),
        "pyautogui": _check_module("pyautogui"),
        "pynput": _check_module("pynput"),
        "opencv": _check_module("cv2"),
    }

    all_core_installed = all(deps[d]["installed"] for d in ["mss", "pyautogui", "pynput"])

    # Determine recommendation
    if all_core_installed:
        recommendation = "ready"
    elif os_info["os"] == "Linux" and os_info.get("display_server") == "wayland":
        recommendation = "limited"
    else:
        recommendation = "install_required"

    # Check setup.json for saved ronin preference
    setup = _read_setup()

    return ApiResponse(
        data={
            **os_info,
            "deps": deps,
            "all_core_installed": all_core_installed,
            "recommendation": recommendation,
            "ronin_enabled_in_setup": setup.get("ronin_enabled", False),
        }
    )


@router.post("/ronin-install", response_model=ApiResponse)
async def install_ronin_deps():
    """Install Ronin desktop control dependencies via pip."""
    if settings.deployment_mode == "server":
        return ApiResponse(
            data={
                "status": "error",
                "message": "Ronin host desktop control is unavailable in Shogun Server mode.",
            }
        )

    import subprocess
    import sys

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", ".[ronin]", "--quiet", "--disable-pip-version-check"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )

        if result.returncode == 0:
            # Re-check what got installed
            deps = {
                "mss": _check_module("mss"),
                "pyautogui": _check_module("pyautogui"),
                "pynput": _check_module("pynput"),
                "opencv": _check_module("cv2"),
            }

            # Update setup.json
            setup = _read_setup()
            setup["ronin_enabled"] = True
            _write_setup(setup)

            return ApiResponse(
                data={
                    "status": "success",
                    "message": "Ronin dependencies installed successfully.",
                    "deps": deps,
                }
            )
        else:
            return ApiResponse(
                data={
                    "status": "error",
                    "message": f"Installation failed: {result.stderr[:500]}",
                    "stdout": result.stdout[:500],
                }
            )
    except subprocess.TimeoutExpired:
        return ApiResponse(
            data={
                "status": "error",
                "message": "Installation timed out after 120 seconds.",
            }
        )
    except Exception as exc:
        return ApiResponse(
            data={
                "status": "error",
                "message": f"Installation error: {str(exc)}",
            }
        )


# Map display names to pip package names
_RONIN_DEP_MAP: dict[str, tuple[str, str]] = {
    "mss": ("mss", "mss"),
    "pyautogui": ("pyautogui", "pyautogui"),
    "pynput": ("pynput", "pynput"),
    "opencv": ("opencv-python-headless", "cv2"),
}


class RoninDepInstallPayload(BaseModel):
    dep_name: str


@router.post("/ronin-install-dep", response_model=ApiResponse)
async def install_single_ronin_dep(payload: RoninDepInstallPayload):
    """Install a single Ronin dependency by name."""
    import subprocess
    import sys

    dep_name = payload.dep_name.lower()
    if dep_name not in _RONIN_DEP_MAP:
        return ApiResponse(
            data={
                "status": "error",
                "message": f"Unknown dependency: {dep_name}. Allowed: {', '.join(_RONIN_DEP_MAP.keys())}",
            }
        )

    pip_package, import_name = _RONIN_DEP_MAP[dep_name]

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pip_package, "--quiet", "--disable-pip-version-check"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )

        if result.returncode == 0:
            info = _check_module(import_name)
            return ApiResponse(
                data={
                    "status": "success",
                    "message": f"{dep_name} installed successfully.",
                    "dep": {dep_name: info},
                }
            )
        else:
            return ApiResponse(
                data={
                    "status": "error",
                    "message": f"Failed to install {dep_name}: {result.stderr[:500]}",
                }
            )
    except subprocess.TimeoutExpired:
        return ApiResponse(
            data={
                "status": "error",
                "message": f"Installation of {dep_name} timed out.",
            }
        )
    except Exception as exc:
        return ApiResponse(
            data={
                "status": "error",
                "message": f"Installation error: {str(exc)}",
            }
        )
