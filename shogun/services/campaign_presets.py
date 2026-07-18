"""Campaign Presets — Named safety configurations for Shogun tool gating.

A Campaign Preset bundles:
- A timeout (minutes, 0 = unlimited)
- A set of per-tool overrides (allow / confirm / block)

Presets come in two flavours:
- Built-in: hardcoded, always available, cannot be deleted
- Custom: stored in data/campaign_presets.json, user-created via API

When a preset is active (set in posture as active_campaign_preset), the
ToolGate checks preset overrides before falling through to the mode × risk
threshold matrix.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger("shogun.campaign_presets")

# ── Built-in Presets ─────────────────────────────────────────────────

BUILTIN_PRESETS: dict[str, dict[str, Any]] = {
    "safe_research": {
        "name": "Safe Research",
        "description": "Read-only research with no external side effects. Browsing and reading are allowed; sending, creating, and desktop control are blocked.",
        "timeout_minutes": 60,
        "is_builtin": True,
        "tool_overrides": {
            "echo_tool":             "allow",
            "tool_list_debug":       "allow",
            "list_available_models": "allow",
            "browse_web":            "allow",
            "take_screenshot":       "allow",
            "fetch_inbox":           "allow",
            "read_email":            "allow",
            "list_calendar_events":  "allow",
            "list_cron_jobs":        "allow",
            "store_memory":          "allow",
            "update_model_settings": "block",
            "send_email":            "block",
            "send_telegram_message": "block",
            "create_calendar_event": "block",
            "create_cron_job":       "block",
            "delete_cron_job":       "block",
            "desktop_screenshot":    "block",
            "desktop_click":         "block",
            "desktop_type":          "block",
            "spawn_samurai":         "block",
            "create_agent_flow":     "block",
            "edit_agent_flow":       "block",
            "create_flow_stack":     "block",
            "edit_flow_stack":       "block",
        },
    },
    "business_pilot": {
        "name": "Business Pilot",
        "description": "Read-heavy with confirmed writes. Browsing and reading are allowed freely; outbound actions (email, calendar, agents) require confirmation; destructive/desktop actions are blocked.",
        "timeout_minutes": 120,
        "is_builtin": True,
        "tool_overrides": {
            "echo_tool":             "allow",
            "tool_list_debug":       "allow",
            "list_available_models": "allow",
            "browse_web":            "allow",
            "take_screenshot":       "allow",
            "fetch_inbox":           "allow",
            "read_email":            "allow",
            "list_calendar_events":  "allow",
            "list_cron_jobs":        "allow",
            "store_memory":          "allow",
            "update_model_settings": "confirm",
            "send_email":            "confirm",
            "send_telegram_message": "confirm",
            "create_calendar_event": "confirm",
            "spawn_samurai":         "confirm",
            "create_agent_flow":     "confirm",
            "edit_agent_flow":       "confirm",
            "create_flow_stack":     "confirm",
            "edit_flow_stack":       "confirm",
            "create_cron_job":       "block",
            "delete_cron_job":       "block",
            "desktop_screenshot":    "block",
            "desktop_click":         "block",
            "desktop_type":          "block",
        },
    },
    "full_autonomous": {
        "name": "Full Autonomous",
        "description": "All tools available with no preset overrides. Use for trusted Agent Flow pipelines or when the operator is actively supervising.",
        "timeout_minutes": 0,
        "is_builtin": True,
        "tool_overrides": {},
    },
}


# ── Custom Preset Storage ────────────────────────────────────────────

def _get_custom_presets_path() -> Path:
    """Get the path to the custom presets JSON file."""
    from shogun.config import settings
    data_dir = Path(getattr(settings, "data_dir", "data"))
    return data_dir / "campaign_presets.json"


def _load_custom_presets() -> dict[str, dict[str, Any]]:
    """Load custom presets from disk."""
    path = _get_custom_presets_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
        log.warning("Custom presets file is not a dict, ignoring")
        return {}
    except Exception as e:
        log.warning("Failed to load custom presets: %s", e)
        return {}


def _save_custom_presets(presets: dict[str, dict[str, Any]]) -> None:
    """Save custom presets to disk."""
    path = _get_custom_presets_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(presets, indent=2), encoding="utf-8")
    except Exception as e:
        log.error("Failed to save custom presets: %s", e)
        raise


# ── Public API ───────────────────────────────────────────────────────

def list_presets() -> list[dict[str, Any]]:
    """List all presets (built-in + custom).

    Returns a list of preset dicts, each containing:
    - key: the preset identifier (slug)
    - name, description, timeout_minutes, is_builtin, tool_overrides
    """
    result = []

    # Built-in presets
    for key, preset in BUILTIN_PRESETS.items():
        result.append({"key": key, **preset})

    # Custom presets
    custom = _load_custom_presets()
    for key, preset in custom.items():
        result.append({"key": key, "is_builtin": False, **preset})

    return result


def get_preset(key: str) -> dict[str, Any] | None:
    """Get a preset by its key (slug). Returns None if not found."""
    # Check built-in first
    if key in BUILTIN_PRESETS:
        return {"key": key, **BUILTIN_PRESETS[key]}

    # Check custom
    custom = _load_custom_presets()
    if key in custom:
        return {"key": key, "is_builtin": False, **custom[key]}

    return None


def create_custom_preset(
    key: str,
    name: str,
    description: str = "",
    timeout_minutes: int = 0,
    tool_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Create a new custom preset.

    Raises ValueError if key conflicts with a built-in preset or already exists.
    """
    if key in BUILTIN_PRESETS:
        raise ValueError(f"Cannot create preset with key '{key}' — conflicts with built-in preset")

    custom = _load_custom_presets()
    if key in custom:
        raise ValueError(f"Custom preset '{key}' already exists. Delete it first to recreate.")

    # Validate override actions
    valid_actions = {"allow", "confirm", "block"}
    overrides = tool_overrides or {}
    for tool, action in overrides.items():
        if action not in valid_actions:
            raise ValueError(f"Invalid action '{action}' for tool '{tool}'. Must be: {valid_actions}")

    preset = {
        "name": name,
        "description": description,
        "timeout_minutes": timeout_minutes,
        "tool_overrides": overrides,
    }
    custom[key] = preset
    _save_custom_presets(custom)

    log.info("Created custom campaign preset: %s (%s)", key, name)
    return {"key": key, "is_builtin": False, **preset}


def delete_custom_preset(key: str) -> bool:
    """Delete a custom preset. Returns True if deleted, False if not found.

    Raises ValueError if attempting to delete a built-in preset.
    """
    if key in BUILTIN_PRESETS:
        raise ValueError(f"Cannot delete built-in preset '{key}'")

    custom = _load_custom_presets()
    if key not in custom:
        return False

    del custom[key]
    _save_custom_presets(custom)
    log.info("Deleted custom campaign preset: %s", key)
    return True
