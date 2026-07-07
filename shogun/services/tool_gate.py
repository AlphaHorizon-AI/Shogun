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

import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

log = logging.getLogger("shogun.tool_gate")

# ── Gensui Central Governance Overrides ──────────────────────────────
# Populated by GensuiClient._sync_policy() when connected to a Gensui server.
# Format: {"tool_name": "allow" | "confirm" | "block"}
_gensui_overrides: dict[str, str] = {}


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
    # Comms — read
    "fetch_inbox":            {"risk": "low",      "category": "comms"},
    "read_email":             {"risk": "low",      "category": "comms"},
    "list_calendar_events":   {"risk": "low",      "category": "comms"},
    "list_cron_jobs":         {"risk": "low",      "category": "comms"},
    # Comms — write
    "send_email":             {"risk": "high",     "category": "comms"},
    "create_calendar_event":  {"risk": "medium",   "category": "comms"},
    "create_cron_job":        {"risk": "high",     "category": "comms"},
    "delete_cron_job":        {"risk": "high",     "category": "comms"},
    # Browser (Mado)
    "browse_web":             {"risk": "low",      "category": "browser"},
    "take_screenshot":        {"risk": "low",      "category": "browser"},
    # Desktop (Ronin)
    "desktop_screenshot":     {"risk": "low",      "category": "desktop"},
    "desktop_click":          {"risk": "high",     "category": "desktop"},
    "desktop_type":           {"risk": "high",     "category": "desktop"},
    # Agents
    "spawn_samurai":          {"risk": "medium",   "category": "agents"},
    # Workflows
    "create_agent_flow":      {"risk": "medium",   "category": "workflow"},
    # Office — Excel (Katana)
    "office_excel_open":          {"risk": "low",      "category": "office"},
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
    for key, value in args.items():
        if not isinstance(value, str):
            continue
        for pattern in _DESTRUCTIVE_COMMAND_PATTERNS:
            if pattern.search(value):
                flags.append(f"destructive_command:{pattern.pattern[:30]}")
                break  # one flag per argument is enough

    return flags


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


# ── Main Gate Function ───────────────────────────────────────────────

async def check_tool_access(
    mode: str,
    tool_name: str,
    args: dict[str, Any],
    campaign_preset: dict | None = None,
) -> GateDecision:
    """Unified ToolGate check — decides allow/confirm/block for a tool call.

    Evaluation order:
    1. Campaign preset override (if active) — highest priority
    2. Parameter-aware destructive checks — can escalate to block/confirm
    3. Static override rules (future: credential entry, payments)
    4. Mode × risk threshold matrix — default fallthrough

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
    preset_action = _resolve_campaign_override(tool_name, campaign_preset)
    if preset_action is not None:
        preset_name = campaign_preset.get("name", "unknown") if campaign_preset else "unknown"
        return GateDecision(
            action=preset_action,
            reason=f"Campaign preset '{preset_name}' override: {preset_action.value}",
            risk_level=risk,
            tool_name=tool_name,
        )

    # ── 1.5. Gensui central governance override ──
    gensui_action_str = _gensui_overrides.get(tool_name)
    if gensui_action_str:
        try:
            gensui_action = GateAction(gensui_action_str)
            return GateDecision(
                action=gensui_action,
                reason=f"Gensui governance override: {gensui_action.value}",
                risk_level=risk,
                tool_name=tool_name,
            )
        except ValueError:
            log.warning("Invalid Gensui override action '%s' for tool '%s'", gensui_action_str, tool_name)

    # ── 2. Parameter-aware destructive checks ──
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

    # ── 3. Static override rules (extensible) ──
    # Reserved for future: payment tools, credential brokering, etc.

    # ── 4. Mode × risk threshold matrix ──
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
