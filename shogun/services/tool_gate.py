"""ToolGate — Unified safety enforcement for tool execution.

This module sits between PostureGuard (which gates which tools are *available*)
and execute_native_tool() (which *runs* them). ToolGate decides *how* each
available tool call is handled: allow, confirm, or block.

Architecture:
    PostureGuard  →  filter_tools_by_posture()  →  which tools appear in the prompt
    ToolGate      →  check_tool_access()        →  per-call enforcement at execution time

The separation is intentional: PostureGuard is a coarse-grained capability lock
(tier-based), while ToolGate is fine-grained per-invocation safety (risk-aware,
parameter-aware, campaign-preset-aware).
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

log = logging.getLogger("shogun.tool_gate")

# ── Gensui Central Governance Overrides ──────────────────────────────
# Populated by GensuiClient._sync_policy() when connected to a Gensui server.
# Format: {"tool_name": "allow" | "confirm" | "block"}
_gensui_overrides: dict[str, str] = {}
_gensui_advanced_controls: dict[str, Any] = {"enabled": False, "rules": []}
_LOCAL_OVERRIDES_PATH = Path("data/toolgate_overrides.json")
_DEFAULT_LOCAL_SCOPE = "global"
_ADVANCED_ACTIONS = {"confirm", "block"}
_ADVANCED_MATCH_TYPES = {"contains", "word"}
_PATH_ARGUMENT_KEYS = {
    "path",
    "file_path",
    "left_path",
    "right_path",
    "input_path",
    "output_path",
    "source_path",
    "destination_path",
    "output_directory",
    "directory",
    "folder",
}
_FILESYSTEM_OPERATIONS = ("read", "write", "create", "delete")
_OUTPUT_PATH_KEYS = {"output_path", "destination_path", "output_directory"}
_NETWORK_MODES = {"disabled", "allowlist", "full"}


def normalize_advanced_controls(config: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and normalize a monotonic advanced content-rule configuration."""
    if not config:
        return {"enabled": False, "rules": []}
    if not isinstance(config, dict):
        raise ValueError("Advanced ToolGate controls must be an object.")

    rules = config.get("rules", [])
    if not isinstance(rules, list):
        raise ValueError("Advanced ToolGate rules must be a list.")
    if len(rules) > 100:
        raise ValueError("Advanced ToolGate supports at most 100 rules per policy.")

    normalized_rules: list[dict[str, Any]] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"Advanced ToolGate rule {index + 1} must be an object.")
        pattern = str(rule.get("pattern", "")).strip()
        if not pattern or len(pattern) > 200:
            raise ValueError(f"Advanced ToolGate rule {index + 1} needs a 1-200 character pattern.")
        action = str(rule.get("action", "confirm")).lower()
        if action not in _ADVANCED_ACTIONS:
            raise ValueError("Advanced ToolGate rules may only confirm or block.")
        match_type = str(rule.get("match_type", "contains")).lower()
        if match_type not in _ADVANCED_MATCH_TYPES:
            raise ValueError("Advanced ToolGate match type must be 'contains' or 'word'.")
        tools = rule.get("tools", [])
        if not isinstance(tools, list) or len(tools) > 50:
            raise ValueError("Advanced ToolGate rule tools must be a list of at most 50 names.")
        tool_names = sorted({str(tool).strip() for tool in tools if str(tool).strip()})
        normalized_rules.append(
            {
                "id": str(rule.get("id") or f"rule-{index + 1}")[:80],
                "label": str(rule.get("label") or pattern)[:120],
                "pattern": pattern,
                "match_type": match_type,
                "action": action,
                "tools": tool_names,
                "case_sensitive": bool(rule.get("case_sensitive", False)),
                "enabled": bool(rule.get("enabled", True)),
            }
        )
    return {"enabled": bool(config.get("enabled", False)), "rules": normalized_rules}


def _load_local_overrides() -> dict[str, dict[str, str]]:
    try:
        if not _LOCAL_OVERRIDES_PATH.exists():
            return {}
        payload = json.loads(_LOCAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        scopes = payload.get("scopes")
        if isinstance(scopes, dict):
            return {
                str(scope): {
                    str(tool): str(action)
                    for tool, action in overrides.items()
                    if action in {"allow", "confirm", "block"}
                }
                for scope, overrides in scopes.items()
                if isinstance(overrides, dict)
            }

        # v1 stored one global map. Keep it available to legacy callers, but
        # new UI/runtime paths always use an explicit tier or policy scope.
        return {
            _DEFAULT_LOCAL_SCOPE: {
                str(tool): str(action)
                for tool, action in payload.items()
                if action in {"allow", "confirm", "block"}
            }
        }
    except Exception as exc:
        log.warning("[ToolGate] Failed to load local overrides: %s", exc)
        return {}


_local_override_scopes: dict[str, dict[str, str]] = _load_local_overrides()


def _load_local_advanced_controls() -> dict[str, dict[str, Any]]:
    try:
        if not _LOCAL_OVERRIDES_PATH.exists():
            return {}
        payload = json.loads(_LOCAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
        scopes = payload.get("advanced_scopes", {}) if isinstance(payload, dict) else {}
        if not isinstance(scopes, dict):
            return {}
        result = {}
        for scope, config in scopes.items():
            try:
                result[str(scope)] = normalize_advanced_controls(config)
            except ValueError as exc:
                log.warning("[ToolGate] Ignoring invalid advanced controls for %s: %s", scope, exc)
        return result
    except Exception as exc:
        log.warning("[ToolGate] Failed to load advanced controls: %s", exc)
        return {}


_local_advanced_scopes: dict[str, dict[str, Any]] = _load_local_advanced_controls()


def normalize_tool_detail(config: dict[str, Any] | None) -> dict[str, list[str]]:
    """Normalize one tool's detailed filesystem boundary."""
    config = config or {}
    if not isinstance(config, dict):
        raise ValueError("Tool detail must be an object.")

    normalized: dict[str, list[str]] = {}
    for key in ("allowed_internal_paths", "allowed_network_paths"):
        values = config.get(key, [])
        if not isinstance(values, list) or len(values) > 50:
            raise ValueError(f"{key} must be a list of at most 50 paths.")
        paths = []
        for value in values:
            path = str(value).strip()
            if not path:
                continue
            if len(path) > 1024:
                raise ValueError("ToolGate allowlist paths may not exceed 1024 characters.")
            if path not in paths:
                paths.append(path)
        normalized[key] = paths
    return normalized


def _load_local_tool_details() -> dict[str, dict[str, dict[str, list[str]]]]:
    try:
        if not _LOCAL_OVERRIDES_PATH.exists():
            return {}
        payload = json.loads(_LOCAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
        scopes = payload.get("detail_scopes", {}) if isinstance(payload, dict) else {}
        if not isinstance(scopes, dict):
            return {}
        result = {}
        for scope, tools in scopes.items():
            if not isinstance(tools, dict):
                continue
            result[str(scope)] = {
                str(tool): normalize_tool_detail(detail)
                for tool, detail in tools.items()
                if isinstance(detail, dict)
            }
        return result
    except Exception as exc:
        log.warning("[ToolGate] Failed to load detailed tool controls: %s", exc)
        return {}


_local_detail_scopes: dict[str, dict[str, dict[str, list[str]]]] = _load_local_tool_details()


def normalize_filesystem_controls(config: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize the shared advanced filesystem policy."""
    config = config or {}
    if not isinstance(config, dict):
        raise ValueError("Filesystem controls must be an object.")
    folders = config.get("folders", [])
    if not isinstance(folders, list) or len(folders) > 100:
        raise ValueError("Filesystem controls support at most 100 folders.")

    normalized_folders = []
    seen: set[tuple[str, str]] = set()
    for index, folder in enumerate(folders):
        if not isinstance(folder, dict):
            raise ValueError(f"Filesystem folder {index + 1} must be an object.")
        path = str(folder.get("path", "")).strip()
        if not path or len(path) > 1024:
            raise ValueError(f"Filesystem folder {index + 1} needs a valid path.")
        kind = str(folder.get("kind", "internal")).lower()
        if kind not in {"internal", "network"}:
            raise ValueError("Filesystem folder kind must be 'internal' or 'network'.")
        identity = (kind, path.casefold())
        if identity in seen:
            continue
        seen.add(identity)
        normalized_folders.append(
            {
                "id": str(folder.get("id") or f"folder-{index + 1}")[:80],
                "path": path,
                "kind": kind,
                **{operation: bool(folder.get(operation, False)) for operation in _FILESYSTEM_OPERATIONS},
            }
        )
    return {"enabled": bool(config.get("enabled", False)), "folders": normalized_folders}


def _tool_default_filesystem_operation(tool_name: str) -> str:
    if tool_name == "workspace_delete":
        return "delete"
    if tool_name == "workspace_mkdir":
        return "create"
    if tool_name == "workspace_write" or tool_name in {
        "file_transform",
        "file_export",
        "file_archive_extract_selected",
    }:
        return "write"
    return "read"


def _legacy_filesystem_controls(
    tools: dict[str, dict[str, list[str]]],
) -> dict[str, Any]:
    """Merge v4 per-tool roots into one conservative folder policy."""
    entries: dict[tuple[str, str], dict[str, Any]] = {}
    for tool_name, detail in tools.items():
        if not isinstance(detail, dict):
            continue
        for key, kind in (
            ("allowed_internal_paths", "internal"),
            ("allowed_network_paths", "network"),
        ):
            for path in detail.get(key, []):
                identity = (kind, str(path).casefold())
                entry = entries.setdefault(
                    identity,
                    {
                        "id": f"migrated-{len(entries) + 1}",
                        "path": str(path),
                        "kind": kind,
                        **{operation: False for operation in _FILESYSTEM_OPERATIONS},
                    },
                )
                operation = _tool_default_filesystem_operation(tool_name)
                entry[operation] = True
                # The legacy write-capable tools could both replace existing
                # files and create new ones. Preserve both capabilities when
                # migrating to the more precise shared permission model.
                if operation == "write":
                    entry["create"] = True
    return {"enabled": bool(entries), "folders": list(entries.values())}


def _load_local_filesystem_controls() -> dict[str, dict[str, Any]]:
    try:
        payload = (
            json.loads(_LOCAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
            if _LOCAL_OVERRIDES_PATH.exists()
            else {}
        )
        scopes = payload.get("filesystem_scopes", {}) if isinstance(payload, dict) else {}
        result = {
            str(scope): normalize_filesystem_controls(config)
            for scope, config in scopes.items()
            if isinstance(config, dict)
        } if isinstance(scopes, dict) else {}
        for scope, tools in _local_detail_scopes.items():
            result.setdefault(scope, _legacy_filesystem_controls(tools))
        return result
    except Exception as exc:
        log.warning("[ToolGate] Failed to load filesystem controls: %s", exc)
        return {}


_local_filesystem_scopes: dict[str, dict[str, Any]] = _load_local_filesystem_controls()


def normalize_network_controls(config: dict[str, Any] | None) -> dict[str, Any]:
    """Normalize the shared ToolGate Internet-access policy."""
    config = config or {}
    if not isinstance(config, dict):
        raise ValueError("Network controls must be an object.")
    mode = str(config.get("mode", "allowlist")).strip().lower()
    if mode not in _NETWORK_MODES:
        raise ValueError("Network mode must be 'disabled', 'allowlist', or 'full'.")
    values = config.get("allowed_domains", [])
    if not isinstance(values, list) or len(values) > 200:
        raise ValueError("Network controls support at most 200 allowed domains.")

    domains = []
    for index, value in enumerate(values):
        domain = str(value).strip().lower().rstrip(".")
        if "://" in domain:
            domain = (urlsplit(domain).hostname or "").lower().rstrip(".")
        if not domain or len(domain) > 253 or any(character.isspace() for character in domain):
            raise ValueError(f"Allowed domain {index + 1} is invalid.")
        wildcard_invalid = (
            "*" in domain
            and domain not in {"*", "*.*"}
            and (not domain.startswith("*.") or "*" in domain[2:])
        )
        if "/" in domain or wildcard_invalid:
            raise ValueError(f"Allowed domain {index + 1} must be a hostname or leading wildcard.")
        if domain not in domains:
            domains.append(domain)
    return {
        "enabled": bool(config.get("enabled", False)),
        "mode": mode,
        "allowed_domains": domains,
    }


def _load_local_network_controls() -> dict[str, dict[str, Any]]:
    try:
        payload = (
            json.loads(_LOCAL_OVERRIDES_PATH.read_text(encoding="utf-8"))
            if _LOCAL_OVERRIDES_PATH.exists()
            else {}
        )
        scopes = payload.get("network_scopes", {}) if isinstance(payload, dict) else {}
        if not isinstance(scopes, dict):
            return {}
        return {
            str(scope): normalize_network_controls(config)
            for scope, config in scopes.items()
            if isinstance(config, dict)
        }
    except Exception as exc:
        log.warning("[ToolGate] Failed to load network controls: %s", exc)
        return {}


_local_network_scopes: dict[str, dict[str, Any]] = _load_local_network_controls()


def _persist_local_policy() -> None:
    _LOCAL_OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp_path = _LOCAL_OVERRIDES_PATH.with_suffix(".tmp")
    temp_path.write_text(
        json.dumps(
            {
                "version": 6,
                "scopes": _local_override_scopes,
                "advanced_scopes": _local_advanced_scopes,
                "detail_scopes": _local_detail_scopes,
                "filesystem_scopes": _local_filesystem_scopes,
                "network_scopes": _local_network_scopes,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    temp_path.replace(_LOCAL_OVERRIDES_PATH)


def set_local_overrides(overrides: dict[str, str], scope: str = _DEFAULT_LOCAL_SCOPE) -> None:
    """Persist standalone ToolGate overrides for one effective tier/policy."""
    invalid = {
        tool: action
        for tool, action in overrides.items()
        if tool not in TOOL_RISK_REGISTRY or action not in {"allow", "confirm", "block"}
    }
    if invalid:
        raise ValueError(f"Invalid ToolGate overrides: {invalid}")

    global _local_override_scopes
    next_scopes = {key: dict(value) for key, value in _local_override_scopes.items()}
    if overrides:
        next_scopes[scope] = dict(sorted(overrides.items()))
    else:
        next_scopes.pop(scope, None)
    _local_override_scopes = next_scopes
    _persist_local_policy()


def get_local_overrides(scope: str = _DEFAULT_LOCAL_SCOPE) -> dict[str, str]:
    """Return locally configured overrides for one effective tier/policy."""
    return dict(_local_override_scopes.get(scope, {}))


def set_local_advanced_controls(
    config: dict[str, Any],
    scope: str = _DEFAULT_LOCAL_SCOPE,
) -> None:
    """Persist advanced content rules for one effective tier/policy."""
    normalized = normalize_advanced_controls(config)
    global _local_advanced_scopes
    next_scopes = {key: dict(value) for key, value in _local_advanced_scopes.items()}
    if normalized["enabled"] or normalized["rules"]:
        next_scopes[scope] = normalized
    else:
        next_scopes.pop(scope, None)
    _local_advanced_scopes = next_scopes
    _persist_local_policy()


def get_local_advanced_controls(scope: str = _DEFAULT_LOCAL_SCOPE) -> dict[str, Any]:
    """Return advanced content rules for one effective tier/policy."""
    config = _local_advanced_scopes.get(scope)
    return normalize_advanced_controls(config)


def set_local_tool_detail(
    tool_name: str,
    config: dict[str, Any],
    scope: str = _DEFAULT_LOCAL_SCOPE,
) -> None:
    """Persist detailed controls for one tool in one effective policy scope."""
    if tool_name not in TOOL_RISK_REGISTRY:
        raise ValueError(f"Unknown ToolGate tool '{tool_name}'.")
    normalized = normalize_tool_detail(config)
    global _local_detail_scopes
    next_scopes = {
        key: {tool: dict(detail) for tool, detail in tools.items()}
        for key, tools in _local_detail_scopes.items()
    }
    details = next_scopes.setdefault(scope, {})
    if normalized["allowed_internal_paths"] or normalized["allowed_network_paths"]:
        details[tool_name] = normalized
    else:
        details.pop(tool_name, None)
    if not details:
        next_scopes.pop(scope, None)
    _local_detail_scopes = next_scopes
    _persist_local_policy()


def get_local_tool_detail(
    tool_name: str,
    scope: str = _DEFAULT_LOCAL_SCOPE,
) -> dict[str, list[str]]:
    """Return normalized detailed controls for one tool and policy scope."""
    return normalize_tool_detail(_local_detail_scopes.get(scope, {}).get(tool_name))


def set_local_filesystem_controls(
    config: dict[str, Any],
    scope: str = _DEFAULT_LOCAL_SCOPE,
) -> None:
    """Persist one shared folder/operation policy for the effective scope."""
    normalized = normalize_filesystem_controls(config)
    global _local_filesystem_scopes
    next_scopes = {key: dict(value) for key, value in _local_filesystem_scopes.items()}
    if normalized["enabled"] or normalized["folders"]:
        next_scopes[scope] = normalized
    else:
        next_scopes.pop(scope, None)
    _local_filesystem_scopes = next_scopes
    _persist_local_policy()


def get_local_filesystem_controls(
    scope: str = _DEFAULT_LOCAL_SCOPE,
) -> dict[str, Any]:
    """Return the shared advanced filesystem policy for one scope."""
    return normalize_filesystem_controls(_local_filesystem_scopes.get(scope))


def set_local_network_controls(
    config: dict[str, Any],
    scope: str = _DEFAULT_LOCAL_SCOPE,
) -> None:
    """Persist one shared Internet-access policy for the effective scope."""
    normalized = normalize_network_controls(config)
    global _local_network_scopes
    next_scopes = {key: dict(value) for key, value in _local_network_scopes.items()}
    if normalized["enabled"] or normalized["allowed_domains"]:
        next_scopes[scope] = normalized
    else:
        next_scopes.pop(scope, None)
    _local_network_scopes = next_scopes
    _persist_local_policy()


def get_local_network_controls(
    scope: str = _DEFAULT_LOCAL_SCOPE,
) -> dict[str, Any]:
    """Return the shared Internet-access policy for one scope."""
    return normalize_network_controls(_local_network_scopes.get(scope))


def get_toolgate_scope(posture: dict[str, Any]) -> dict[str, str | None]:
    """Return the stable ToolGate scope for the effective Torii policy."""
    policy_id = posture.get("active_policy_id")
    is_builtin = posture.get("active_policy_is_builtin")
    base_tier = str(posture.get("active_policy_tier") or posture.get("active_tier") or "tactical")
    policy_name = posture.get("active_policy_name")

    if policy_id and is_builtin is False:
        return {
            "key": f"policy:{policy_id}",
            "kind": "custom_policy",
            "label": str(policy_name or "Custom policy"),
            "base_tier": base_tier,
            "policy_id": str(policy_id),
        }
    return {
        "key": f"tier:{base_tier}",
        "kind": "tier",
        "label": base_tier.upper(),
        "base_tier": base_tier,
        "policy_id": str(policy_id) if policy_id else None,
    }


def calculate_capability_risk(permissions: dict[str, Any] | None) -> int:
    """Calculate a stable 0-100 exposure score for capability boundaries."""
    if not permissions:
        return 0

    score = 0

    def add(category: str, key: str, risky_values: set[Any], weight: int) -> None:
        nonlocal score
        value = permissions.get(category, {}).get(key)
        if value in risky_values:
            score += weight

    add("filesystem", "mode", {"full"}, 15)
    add("filesystem", "allow_home_access", {True}, 10)
    add("filesystem", "allow_arbitrary_paths", {True}, 15)
    add("network", "mode", {"full"}, 15)
    add("network", "allow_arbitrary_requests", {True}, 10)
    add("shell", "enabled", {True}, 15)
    add("skills", "allow_auto_install", {True}, 5)
    add("skills", "allow_untrusted", {True}, 10)
    add("subagents", "allow_spawn", {True}, 5)
    add("subagents", "allow_auto_spawn", {True}, 10)
    add("memory", "allow_bulk_delete", {True}, 10)
    for category in ("agentflow", "flow_stack"):
        add(category, "allow_create", {True}, 5)
        add(category, "allow_activate", {True}, 5)
        add(category, "allow_execute", {True}, 10 if category == "flow_stack" else 5)
        add(category, "allow_delete", {True}, 5)

    add("filesystem", "mode", {"scoped", "disabled"}, -5)
    add("network", "mode", {"disabled"}, -10)
    add("shell", "enabled", {False}, -5)
    add("skills", "require_approval", {True}, -5)
    return max(0, min(100, score))


def apply_gensui_overrides(overrides: dict[str, str]) -> None:
    """Set tool-level overrides pushed from Gensui central governance.

    Called by GensuiClient when it receives tool_overrides in the
    effective posture payload during policy sync.
    """
    global _gensui_overrides
    _gensui_overrides = dict(overrides) if overrides else {}
    if _gensui_overrides:
        log.info("[ToolGate] Applied %d Gensui governance overrides", len(_gensui_overrides))


def get_gensui_overrides() -> dict[str, str]:
    """Return current Gensui overrides (for diagnostics/API)."""
    return dict(_gensui_overrides)


def apply_gensui_advanced_controls(config: dict[str, Any] | None) -> None:
    """Apply centrally managed advanced content rules, including cached policy."""
    global _gensui_advanced_controls
    _gensui_advanced_controls = normalize_advanced_controls(config)
    if _gensui_advanced_controls["enabled"]:
        log.info(
            "[ToolGate] Applied %d Gensui advanced content rules",
            len(_gensui_advanced_controls["rules"]),
        )


def get_gensui_advanced_controls() -> dict[str, Any]:
    """Return centrally managed advanced controls for diagnostics/API."""
    return normalize_advanced_controls(_gensui_advanced_controls)


# ── Risk Levels ──────────────────────────────────────────────────────


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GateAction(str, Enum):
    ALLOW = "allow"
    CONFIRM = "confirm"
    BLOCK = "block"


@dataclass
class GateDecision:
    """Result of a ToolGate check."""

    action: GateAction
    reason: str
    risk_level: RiskLevel = RiskLevel.LOW
    tool_name: str = ""
    parameter_flags: list[str] = field(default_factory=list)


# ── Tool Risk Registry ───────────────────────────────────────────────
# Maps every native tool → risk level + category.
# Risk levels:
#   low      — read-only, no side effects (browse, fetch, list)
#   medium   — creates/modifies internal state (memory, settings, events)
#   high     — external side effects or control actions (email, desktop, cron)
#   critical — destructive or irreversible (mass delete, admin escalation)

TOOL_RISK_REGISTRY: dict[str, dict[str, str]] = {
    # Debug
    "echo_tool":              {"risk": "low",      "category": "debug"},
    "tool_list_debug":        {"risk": "low",      "category": "debug"},
    # System
    "list_available_models":  {"risk": "low",      "category": "system"},
    "update_model_settings":  {"risk": "medium",   "category": "system"},
    # Memory
    "store_memory":           {"risk": "medium",   "category": "memory"},
    "reminder_board_add":     {"risk": "medium",   "category": "memory"},
    "reminder_board_list":    {"risk": "low",      "category": "memory"},
    "reminder_board_update":  {"risk": "medium",   "category": "memory"},
    "set_agent_flow_status":  {"risk": "medium",   "category": "workflow"},
    # File format adapters
    "file_detect_type":       {"risk": "low",      "category": "files"},
    "file_inspect":           {"risk": "low",      "category": "files"},
    "file_read":              {"risk": "low",      "category": "files"},
    "file_preview":           {"risk": "low",      "category": "files"},
    "file_schema":            {"risk": "low",      "category": "files"},
    "file_query":             {"risk": "low",      "category": "files"},
    "file_extract":           {"risk": "low",      "category": "files"},
    "file_compare":           {"risk": "low",      "category": "files"},
    "file_validate":          {"risk": "low",      "category": "files"},
    "file_transform":         {"risk": "medium",   "category": "files"},
    "file_export":            {"risk": "medium",   "category": "files"},
    "file_archive_extract_selected": {"risk": "high", "category": "files"},
    "file_index_profile":     {"risk": "medium",   "category": "files"},
    "file_index":             {"risk": "medium",   "category": "files"},
    "file_list_formats":      {"risk": "low",      "category": "files"},
    # Persistent agent workspace
    "workspace_info":         {"risk": "low",      "category": "workspace"},
    "workspace_list":         {"risk": "low",      "category": "workspace"},
    "workspace_read":         {"risk": "low",      "category": "workspace"},
    "workspace_read_image":   {"risk": "low",      "category": "workspace"},
    "workspace_read_pdf":     {"risk": "low",      "category": "workspace"},
    "workspace_write":        {"risk": "medium",   "category": "workspace"},
    "workspace_mkdir":        {"risk": "medium",   "category": "workspace"},
    "workspace_delete":       {"risk": "critical", "category": "workspace"},
    # Comms — read
    "fetch_inbox":            {"risk": "low",      "category": "comms"},
    "read_email":             {"risk": "low",      "category": "comms"},
    "list_calendar_events":   {"risk": "low",      "category": "comms"},
    "list_cron_jobs":         {"risk": "low",      "category": "comms"},
    # Comms — write
    "send_email":             {"risk": "high",     "category": "comms"},
    "send_telegram_message":  {"risk": "high",     "category": "comms"},
    "create_calendar_event":  {"risk": "medium",   "category": "comms"},
    "create_cron_job":        {"risk": "high",     "category": "comms"},
    "delete_cron_job":        {"risk": "high",     "category": "comms"},
    # Browser (Mado)
    "browse_web":             {"risk": "low",      "category": "browser"},
    "take_screenshot":        {"risk": "low",      "category": "browser"},
    "ide_memory_search":      {"risk": "low",      "category": "ide"},
    "ide_memory_store":       {"risk": "medium",   "category": "ide"},
    "ide_memory_reinforce":   {"risk": "low",      "category": "ide"},
    # Desktop (Ronin)
    "desktop_screenshot":     {"risk": "low",      "category": "desktop"},
    "desktop_click":          {"risk": "high",     "category": "desktop"},
    "desktop_type":           {"risk": "high",     "category": "desktop"},
    # Agents
    "spawn_samurai":          {"risk": "medium",   "category": "agents"},
    # Workflows
    "list_agent_flows":        {"risk": "low",      "category": "workflow"},
    "get_agent_flow":          {"risk": "low",      "category": "workflow"},
    "get_flow_stack":          {"risk": "low",      "category": "workflow"},
    "create_agent_flow":      {"risk": "medium",   "category": "workflow"},
    "edit_agent_flow":        {"risk": "medium",   "category": "workflow"},
    "patch_agent_flow":       {"risk": "medium",   "category": "workflow"},
    "delete_agent_flow":      {"risk": "high",     "category": "workflow"},
    "create_flow_stack":      {"risk": "medium",   "category": "workflow"},
    "edit_flow_stack":        {"risk": "medium",   "category": "workflow"},
    "delete_flow_stack":      {"risk": "high",     "category": "workflow"},
    # Skills
    "skills_request_activation": {"risk": "low",   "category": "skills"},
    "skills_explain_active":     {"risk": "low",   "category": "skills"},
    "skills_report_outcome":     {"risk": "low",   "category": "skills"},
    "mcp_list_tools":         {"risk": "low",      "category": "mcp"},
    "mcp_call_tool":          {"risk": "high",     "category": "mcp"},
    "mcp_list_resources":     {"risk": "low",      "category": "mcp"},
    "mcp_read_resource":      {"risk": "low",      "category": "mcp"},
    # Office — Excel (Katana)
    "office_excel_open":          {"risk": "low",      "category": "office"},
    "office_excel_open_attachment": {"risk": "low",    "category": "office"},
    "office_excel_read_range":    {"risk": "low",      "category": "office"},
    "office_excel_write_range":   {"risk": "medium",   "category": "office"},
    "office_excel_calculate":     {"risk": "low",      "category": "office"},
    "office_excel_save_as":       {"risk": "medium",   "category": "office"},
    "office_excel_export_pdf":    {"risk": "medium",   "category": "office"},
    "office_excel_list_sheets":   {"risk": "low",      "category": "office"},
    "office_excel_get_metadata":  {"risk": "low",      "category": "office"},
    # Office — Word (Katana)
    "office_word_open":                  {"risk": "low",      "category": "office"},
    "office_word_replace_placeholders":  {"risk": "medium",   "category": "office"},
    "office_word_insert_table":          {"risk": "medium",   "category": "office"},
    "office_word_save_as":               {"risk": "medium",   "category": "office"},
    "office_word_export_pdf":            {"risk": "medium",   "category": "office"},
    "office_word_get_metadata":          {"risk": "low",      "category": "office"},
    "office_word_read_text":              {"risk": "low",      "category": "office"},
    "office_word_read_page":              {"risk": "low",      "category": "office"},
    "office_word_read_pages":             {"risk": "low",      "category": "office"},
    "office_word_read_headings":          {"risk": "low",      "category": "office"},
    "office_word_insert_paragraph":       {"risk": "medium",   "category": "office"},
    "office_word_create":                 {"risk": "medium",   "category": "office"},
    "office_word_create_from_text":       {"risk": "medium",   "category": "office"},
    # Office — PowerPoint (Katana)
    "office_pptx_open":                  {"risk": "low",      "category": "office"},
    "office_pptx_replace_placeholders":  {"risk": "medium",   "category": "office"},
    "office_pptx_insert_image":          {"risk": "medium",   "category": "office"},
    "office_pptx_insert_table":          {"risk": "medium",   "category": "office"},
    "office_pptx_save_as":               {"risk": "medium",   "category": "office"},
    "office_pptx_export_pdf":            {"risk": "medium",   "category": "office"},
    "office_pptx_get_metadata":          {"risk": "low",      "category": "office"},
    # Office — Outlook (Katana)
    "office_outlook_create_draft":   {"risk": "medium",   "category": "office"},
    "office_outlook_attach_file":    {"risk": "medium",   "category": "office"},
    "office_outlook_save_draft":     {"risk": "medium",   "category": "office"},
    "office_outlook_send":           {"risk": "high",     "category": "office"},
}


def get_tool_risk(tool_name: str) -> RiskLevel:
    """Look up the risk level for a tool. Unknown tools default to MEDIUM."""
    entry = TOOL_RISK_REGISTRY.get(tool_name)
    if entry:
        return RiskLevel(entry["risk"])
    return RiskLevel.MEDIUM


def get_tool_category(tool_name: str) -> str:
    """Look up the category for a tool. Unknown tools default to 'unknown'."""
    entry = TOOL_RISK_REGISTRY.get(tool_name)
    return entry["category"] if entry else "unknown"


# ── Mode Threshold Matrix ────────────────────────────────────────────
# Defines the default gate action for each (mode × risk_level) combination.
#
# Modes:
#   standard       — normal Shogun operation (Shrine through Campaign tiers)
#   ronin_browser  — Ronin tier, browser actions
#   ronin_desktop  — Ronin tier, desktop control actions

MODE_THRESHOLDS: dict[str, dict[str, GateAction]] = {
    "standard": {
        "low":      GateAction.ALLOW,
        "medium":   GateAction.ALLOW,
        "high":     GateAction.CONFIRM,
        "critical": GateAction.BLOCK,
    },
    "campaign": {
        "low":      GateAction.ALLOW,
        "medium":   GateAction.ALLOW,
        "high":     GateAction.ALLOW,
        "critical": GateAction.BLOCK,
    },
    "ronin_browser": {
        "low":      GateAction.ALLOW,
        "medium":   GateAction.ALLOW,
        "high":     GateAction.ALLOW,
        "critical": GateAction.CONFIRM,
    },
    "ronin_desktop": {
        "low":      GateAction.ALLOW,
        "medium":   GateAction.ALLOW,
        "high":     GateAction.CONFIRM,
        "critical": GateAction.BLOCK,
    },
}


# ── Parameter-Aware Destructive Action Checks ────────────────────────

# Patterns that indicate destructive shell/terminal commands
_DESTRUCTIVE_COMMAND_PATTERNS = [
    re.compile(r"\brm\s+(-rf?|--recursive)\b", re.IGNORECASE),
    re.compile(r"\bdel\s+/[sq]\b", re.IGNORECASE),
    re.compile(r"\brmdir\s+/s\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\bDROP\s+(TABLE|DATABASE|SCHEMA)\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b.*\bWHERE\s+1\s*=\s*1\b", re.IGNORECASE),
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    re.compile(r"\bdd\s+if=", re.IGNORECASE),
    re.compile(r"\b(shutdown|reboot|halt|poweroff)\b", re.IGNORECASE),
]

# These tools deliver prose. Their message bodies can legitimately quote words
# such as "shutdown" or "halt"; the text is not executed as a command.
_DESTRUCTIVE_CONTENT_EXEMPT_TOOLS = {
    "channel_send",
    "send_telegram_message",
}

# Patterns that look like credentials or secrets in argument values
_CREDENTIAL_PATTERNS = [
    re.compile(r"(password|passwd|secret|token|api_key|apikey|access_key|private_key)", re.IGNORECASE),
]


def check_dangerous_parameters(tool_name: str, args: dict[str, Any]) -> list[str]:
    """Inspect tool arguments for dangerous patterns.

    Returns a list of flag strings describing what was detected.
    Empty list means no dangerous patterns found.
    """
    flags: list[str] = []

    # ── Check for paths outside workspace ──
    for key, value in args.items():
        if not isinstance(value, str):
            continue

        # Path-like arguments that reference sensitive system dirs
        if key in ("path", "file_path", "target", "directory", "folder"):
            normalized = value.replace("\\", "/").lower()
            sensitive_dirs = [
                "/windows/system32", "/system32",
                "/etc/", "/usr/", "/var/",
                "c:/windows", "c:/program files",
                "/root/", "/home/",
            ]
            for sd in sensitive_dirs:
                if normalized.startswith(sd) or sd in normalized:
                    flags.append(f"sensitive_path:{value}")
                    break

    # ── Check for recursive delete flags ──
    for key, value in args.items():
        if key == "recursive" and value is True:
            flags.append("recursive_delete")
        if isinstance(value, str) and "--force" in value:
            flags.append("force_flag")

    # ── Check for mass operations ──
    for key, value in args.items():
        if key in ("available_tools", "required_capabilities", "tags"):
            continue
        if isinstance(value, list) and len(value) > 10:
            flags.append(f"mass_operation:{key}({len(value)} items)")

    # ── Check desktop_type / desktop_click for credential-like content ──
    if tool_name == "desktop_type":
        text = args.get("text", "")
        if isinstance(text, str):
            for pattern in _CREDENTIAL_PATTERNS:
                if pattern.search(text):
                    flags.append("credential_entry_detected")
                    break

    # ── Check for destructive shell command patterns in any string arg ──
    if tool_name not in _DESTRUCTIVE_CONTENT_EXEMPT_TOOLS:
        for key, value in args.items():
            if not isinstance(value, str):
                continue
            for pattern in _DESTRUCTIVE_COMMAND_PATTERNS:
                if pattern.search(value):
                    flags.append(f"destructive_command:{pattern.pattern[:30]}")
                    break  # one flag per argument is enough

    return flags


def _iter_argument_strings(value: Any, path: str = "$"):
    """Yield string arguments and their JSON-like paths without exposing values."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, nested in value.items():
            yield from _iter_argument_strings(nested, f"{path}.{key}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _iter_argument_strings(nested, f"{path}[{index}]")


def _advanced_rule_matches(rule: dict[str, Any], text: str) -> bool:
    pattern = rule["pattern"]
    candidate = text
    flags = 0 if rule.get("case_sensitive") else re.IGNORECASE
    if rule["match_type"] == "word":
        return re.search(rf"(?<!\w){re.escape(pattern)}(?!\w)", candidate, flags) is not None
    if flags:
        return pattern.casefold() in candidate.casefold()
    return pattern in candidate


def evaluate_advanced_controls(
    tool_name: str,
    args: dict[str, Any],
    local_scope: str = _DEFAULT_LOCAL_SCOPE,
) -> tuple[GateAction | None, str | None, list[str]]:
    """Evaluate local and Gensui content rules and return the strictest match."""
    candidates: list[tuple[str, dict[str, Any], str]] = []
    configurations = (
        ("local", get_local_advanced_controls(local_scope)),
        ("gensui", get_gensui_advanced_controls()),
    )
    argument_strings = list(_iter_argument_strings(args))
    for source, config in configurations:
        if not config["enabled"]:
            continue
        for rule in config["rules"]:
            if not rule["enabled"]:
                continue
            tools = rule.get("tools", [])
            if tools and tool_name not in tools:
                continue
            for path, text in argument_strings:
                if _advanced_rule_matches(rule, text):
                    candidates.append((source, rule, path))
                    break

    if not candidates:
        return None, None, []

    action = max(
        (GateAction(rule["action"]) for _, rule, _ in candidates),
        key=_ACTION_RESTRICTIVENESS.get,
    )
    matched = [
        (source, rule, path)
        for source, rule, path in candidates
        if GateAction(rule["action"]) == action
    ]
    labels = ", ".join(f"{source}:{rule['label']}" for source, rule, _ in matched)
    flags = [
        f"advanced_rule:{source}:{rule['id']}:{path}"
        for source, rule, path in candidates
    ]
    return action, f"Advanced content rule matched ({labels}): {action.value}", flags


def tool_supports_path_controls(tool_name: str) -> bool:
    """Return whether ToolGate can enforce filesystem roots for this tool."""
    return get_tool_category(tool_name) in {"files", "workspace"}


def get_tool_allowed_roots(
    tool_name: str,
    local_scope: str = _DEFAULT_LOCAL_SCOPE,
) -> list[Path]:
    """Resolve shared (or legacy per-tool) roots without requiring them to exist."""
    from shogun.config import settings

    filesystem = get_local_filesystem_controls(local_scope)
    if filesystem["enabled"]:
        roots = []
        for folder in filesystem["folders"]:
            candidate = Path(folder["path"])
            if folder["kind"] == "internal" and not candidate.is_absolute():
                candidate = settings.workspace_path / candidate
            roots.append(candidate.resolve())
        return roots

    detail = get_local_tool_detail(tool_name, local_scope)
    roots: list[Path] = []
    for value in detail["allowed_internal_paths"]:
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = settings.workspace_path / candidate
        roots.append(candidate.resolve())
    for value in detail["allowed_network_paths"]:
        roots.append(Path(value).resolve())
    return roots


def _filesystem_candidate(raw_value: str, kind: str = "internal") -> Path:
    from shogun.config import settings

    candidate = Path(raw_value.strip())
    if kind == "internal" and not candidate.is_absolute():
        candidate = settings.workspace_path / candidate
    # Normalize lexically without querying a user-selected filesystem path.  The
    # execution layer performs a second real-path containment check immediately
    # before any actual file operation.
    return Path(os.path.abspath(os.fspath(candidate)))


def _required_filesystem_operation(
    tool_name: str,
    key: str,
) -> str:
    if tool_name == "workspace_delete":
        return "delete"
    if tool_name == "workspace_mkdir":
        return "create"
    if tool_name == "workspace_write" or key in _OUTPUT_PATH_KEYS:
        return "write"
    return "read"


def evaluate_tool_path_controls(
    tool_name: str,
    args: dict[str, Any],
    local_scope: str = _DEFAULT_LOCAL_SCOPE,
) -> tuple[bool, list[str]]:
    """Require path arguments to stay inside a tool's configured allowlist."""
    if not tool_supports_path_controls(tool_name):
        return True, []
    filesystem = get_local_filesystem_controls(local_scope)
    if not filesystem["enabled"]:
        roots = get_tool_allowed_roots(tool_name, local_scope)
        if not roots:
            return True, []
        flags = []
        for key, raw_value in args.items():
            if key not in _PATH_ARGUMENT_KEYS or not isinstance(raw_value, str) or not raw_value.strip():
                continue
            candidate = _filesystem_candidate(raw_value)
            if not any(candidate == root or root in candidate.parents for root in roots):
                flags.append(f"path_not_allowlisted:$.{key}")
        return not flags, flags

    configured = []
    for folder in filesystem["folders"]:
        root = _filesystem_candidate(folder["path"], folder["kind"])
        configured.append((root, folder))

    candidates: list[tuple[str, Path, str | None]] = []
    for key, raw_value in args.items():
        if key not in _PATH_ARGUMENT_KEYS or not isinstance(raw_value, str) or not raw_value.strip():
            continue
        candidate = _filesystem_candidate(raw_value)
        candidates.append((key, candidate, None))

    if tool_name in {"file_transform", "file_export"}:
        from shogun.config import settings

        filename = Path(str(args.get("output_filename") or "transformed-output")).name
        output = (settings.workspace_path / filename).resolve()
        candidates.append(("output_filename", output, "create"))
    elif tool_name == "file_archive_extract_selected" and not args.get("output_directory"):
        from shogun.config import settings

        source = Path(str(args.get("path") or "archive"))
        output = (settings.workspace_path / f"extracted-{source.stem}").resolve()
        candidates.append(("output_directory", output, "create"))

    flags = []
    for key, candidate, required_operation in candidates:
        matching_folders = [
            folder
            for root, folder in configured
            if candidate == root or root in candidate.parents
        ]
        if not matching_folders:
            flags.append(f"filesystem_permission_denied:read:$.{key}")
            continue
        operations = (
            ("write", "create")
            if required_operation is None and tool_name == "workspace_write"
            else (required_operation or _required_filesystem_operation(tool_name, key),)
        )
        missing_operation = next(
            (
                operation
                for operation in operations
                if not any(bool(folder[operation]) for folder in matching_folders)
            ),
            None,
        )
        if missing_operation:
            flags.append(f"filesystem_permission_denied:{missing_operation}:$.{key}")
    return not flags, flags


# ── Shared Internet Access Controls ──────────────────────────────────

def _network_domains(value: Any) -> list[str]:
    """Collect HTTP(S) hostnames from arbitrarily nested tool arguments."""
    domains: list[str] = []
    if isinstance(value, dict):
        for nested in value.values():
            domains.extend(_network_domains(nested))
    elif isinstance(value, list):
        for nested in value:
            domains.extend(_network_domains(nested))
    elif isinstance(value, str) and value.strip().lower().startswith(("http://", "https://")):
        hostname = (urlsplit(value.strip()).hostname or "").lower().rstrip(".")
        if hostname:
            domains.append(hostname)
    return domains


def _domain_is_allowed(domain: str, allowed_domains: list[str]) -> bool:
    domain = domain.lower().rstrip(".")
    for pattern in allowed_domains:
        pattern = pattern.lower().rstrip(".")
        if pattern in {"*", "*.*"}:
            return True
        if pattern.startswith("*."):
            suffix = pattern[2:]
            if domain == suffix or domain.endswith(f".{suffix}"):
                return True
        elif domain == pattern:
            return True
    return False


def evaluate_tool_network_controls(
    tool_name: str,
    args: dict[str, Any],
    local_scope: str = _DEFAULT_LOCAL_SCOPE,
) -> tuple[bool, list[str]]:
    """Enforce shared Internet mode and domain allowlist for network-capable calls."""
    controls = get_local_network_controls(local_scope)
    if not controls["enabled"] or controls["mode"] == "full":
        return True, []

    network_tool = get_tool_category(tool_name) in {"browser", "mcp"}
    domains = sorted(set(_network_domains(args)))
    if controls["mode"] == "disabled" and (network_tool or domains):
        return False, ["network_access_disabled"]
    if controls["mode"] != "allowlist":
        return True, []
    blocked = [
        f"network_domain_not_allowlisted:{domain}"
        for domain in domains
        if not _domain_is_allowed(domain, controls["allowed_domains"])
    ]
    return not blocked, blocked


# ── Campaign Preset Override Resolution ──────────────────────────────

def _resolve_campaign_override(
    tool_name: str,
    campaign_preset: dict | None,
) -> GateAction | None:
    """Check if a campaign preset has an explicit override for this tool.

    Returns the override action, or None if the preset doesn't override this tool.
    """
    if not campaign_preset:
        return None
    overrides = campaign_preset.get("tool_overrides", {})
    action_str = overrides.get(tool_name)
    if action_str:
        try:
            return GateAction(action_str)
        except ValueError:
            log.warning("Invalid campaign override action '%s' for tool '%s'", action_str, tool_name)
    return None


_ACTION_RESTRICTIVENESS = {
    GateAction.ALLOW: 0,
    GateAction.CONFIRM: 1,
    GateAction.BLOCK: 2,
}


def resolve_explicit_overrides(
    tool_name: str,
    campaign_preset: dict | None = None,
    local_scope: str = _DEFAULT_LOCAL_SCOPE,
) -> tuple[GateAction | None, str | None, dict[str, str | None]]:
    """Merge explicit policy layers without allowing a weaker layer to relax a stricter one."""
    candidates: list[tuple[str, GateAction]] = []
    campaign_action = _resolve_campaign_override(tool_name, campaign_preset)
    local_action_str = get_local_overrides(local_scope).get(tool_name)
    gensui_action_str = _gensui_overrides.get(tool_name)

    if campaign_action is not None:
        candidates.append(("campaign", campaign_action))
    if local_action_str:
        try:
            candidates.append(("local", GateAction(local_action_str)))
        except ValueError:
            log.warning("Invalid local override action '%s' for tool '%s'", local_action_str, tool_name)
    if gensui_action_str:
        try:
            candidates.append(("gensui", GateAction(gensui_action_str)))
        except ValueError:
            log.warning("Invalid Gensui override action '%s' for tool '%s'", gensui_action_str, tool_name)

    detail = {
        "campaign": campaign_action.value if campaign_action else None,
        "local": local_action_str,
        "gensui": gensui_action_str,
    }
    if not candidates:
        return None, None, detail

    action = max((candidate[1] for candidate in candidates), key=_ACTION_RESTRICTIVENESS.get)
    sources = [source for source, candidate in candidates if candidate == action]
    reason = f"Most restrictive explicit override ({', '.join(sources)}): {action.value}"
    return action, reason, detail


# ── Main Gate Function ───────────────────────────────────────────────

async def check_tool_access(
    mode: str,
    tool_name: str,
    args: dict[str, Any],
    campaign_preset: dict | None = None,
    local_scope: str = _DEFAULT_LOCAL_SCOPE,
) -> GateDecision:
    """Unified ToolGate check — decides allow/confirm/block for a tool call.

    Evaluation order:
    1. Campaign preset override (if active) — highest priority
    2. Parameter-aware destructive checks — can escalate to block/confirm
    3. Advanced policy-scoped content rules
    4. Explicit tool override or mode × risk threshold

    Args:
        mode: Operating mode ("standard", "ronin_browser", "ronin_desktop")
        tool_name: Name of the native tool being invoked
        args: The arguments the LLM wants to pass to the tool
        campaign_preset: Active campaign preset dict (or None)

    Returns:
        GateDecision with action, reason, risk_level, and any parameter flags
    """
    risk = get_tool_risk(tool_name)

    # ── 1. Campaign preset override ──
    explicit_action, explicit_reason, _ = resolve_explicit_overrides(
        tool_name,
        campaign_preset,
        local_scope,
    )
    if explicit_action == GateAction.BLOCK:
        return GateDecision(
            action=GateAction.BLOCK,
            reason=explicit_reason or "Explicit override: block",
            risk_level=risk,
            tool_name=tool_name,
        )

    path_allowed, path_flags = evaluate_tool_path_controls(tool_name, args, local_scope)
    if not path_allowed:
        return GateDecision(
            action=GateAction.BLOCK,
            reason="The shared filesystem policy does not grant the required folder operation.",
            risk_level=RiskLevel.CRITICAL,
            tool_name=tool_name,
            parameter_flags=path_flags,
        )

    # ── 1.5. Gensui central governance override ──
    # ── 2. Parameter-aware destructive checks ──
    network_allowed, network_flags = evaluate_tool_network_controls(tool_name, args, local_scope)
    if not network_allowed:
        return GateDecision(
            action=GateAction.BLOCK,
            reason="The shared Internet-access policy does not permit this network target.",
            risk_level=RiskLevel.CRITICAL,
            tool_name=tool_name,
            parameter_flags=network_flags,
        )

    param_flags = check_dangerous_parameters(tool_name, args)
    if param_flags:
        # Destructive commands → block
        if any("destructive_command" in f for f in param_flags):
            return GateDecision(
                action=GateAction.BLOCK,
                reason=f"Destructive command pattern detected: {param_flags}",
                risk_level=RiskLevel.CRITICAL,
                tool_name=tool_name,
                parameter_flags=param_flags,
            )
        # Sensitive paths → block
        if any("sensitive_path" in f for f in param_flags):
            return GateDecision(
                action=GateAction.BLOCK,
                reason=f"Operation targets sensitive system path: {param_flags}",
                risk_level=RiskLevel.CRITICAL,
                tool_name=tool_name,
                parameter_flags=param_flags,
            )
        # Mass operations → confirm
        if any("mass_operation" in f for f in param_flags):
            return GateDecision(
                action=GateAction.CONFIRM,
                reason=f"Mass operation detected: {param_flags}",
                risk_level=RiskLevel.HIGH,
                tool_name=tool_name,
                parameter_flags=param_flags,
            )
        # Credential entry → confirm
        if any("credential" in f for f in param_flags):
            return GateDecision(
                action=GateAction.CONFIRM,
                reason=f"Credential-like content detected: {param_flags}",
                risk_level=RiskLevel.HIGH,
                tool_name=tool_name,
                parameter_flags=param_flags,
            )
        # Recursive delete / force flags → confirm
        if any(f in ("recursive_delete", "force_flag") for f in param_flags):
            return GateDecision(
                action=GateAction.CONFIRM,
                reason=f"Potentially destructive flags: {param_flags}",
                risk_level=RiskLevel.HIGH,
                tool_name=tool_name,
                parameter_flags=param_flags,
            )

    # ── 3. Policy-scoped advanced content rules ──
    advanced_action, advanced_reason, advanced_flags = evaluate_advanced_controls(
        tool_name,
        args,
        local_scope,
    )
    if advanced_action is not None:
        param_flags.extend(advanced_flags)
        if (
            explicit_action is not None
            and _ACTION_RESTRICTIVENESS[explicit_action]
            > _ACTION_RESTRICTIVENESS[advanced_action]
        ):
            advanced_action = explicit_action
            advanced_reason = explicit_reason
        return GateDecision(
            action=advanced_action,
            reason=advanced_reason or f"Advanced content rule: {advanced_action.value}",
            risk_level=RiskLevel.CRITICAL if advanced_action == GateAction.BLOCK else RiskLevel.HIGH,
            tool_name=tool_name,
            parameter_flags=param_flags,
        )

    # ── 4. Explicit tool override ──
    if explicit_action is not None:
        return GateDecision(
            action=explicit_action,
            reason=explicit_reason or f"Explicit override: {explicit_action.value}",
            risk_level=risk,
            tool_name=tool_name,
            parameter_flags=param_flags,
        )

    # ── 5. Mode × risk threshold matrix ──
    thresholds = MODE_THRESHOLDS.get(mode, MODE_THRESHOLDS["standard"])
    action = thresholds.get(risk.value, GateAction.CONFIRM)

    return GateDecision(
        action=action,
        reason=f"Mode '{mode}' threshold for risk '{risk.value}': {action.value}",
        risk_level=risk,
        tool_name=tool_name,
        parameter_flags=param_flags,
    )


# ── Utility: Risk-Aware Tool Filtering ───────────────────────────────

def get_risk_metadata_for_tools(tools: list[dict]) -> dict[str, dict]:
    """Return risk metadata for a list of tool definitions.

    Useful for injecting risk info into audit events or system prompts.
    """
    result = {}
    for tool in tools:
        name = tool["function"]["name"]
        result[name] = {
            "risk": get_tool_risk(name).value,
            "category": get_tool_category(name),
        }
    return result
