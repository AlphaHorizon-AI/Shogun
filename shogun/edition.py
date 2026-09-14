"""Product-edition capabilities for the public Yellow Label release.

The White Label repository retains the complete commercial feature set.  This
repository deliberately ships a fixed, non-configurable Yellow Label boundary
so environment variables or stale configuration cannot re-enable removed
commercial features after an upgrade.
"""

from __future__ import annotations

EDITION_NAME = "yellow-label"

REMOVED_FEATURES = frozenset(
    {
        "flow_stack",
        "team_mode",
        "microsoft_teams",
        "logs_ui",
        "nexus",
        "gensui",
        # Enterprise / Gensui sub-capabilities (SkillOpt Lab §12)
        "gensui_skill_repository",
        "gensui_skill_publication",
        "gensui_skill_distribution",
        "gensui_competence_registry",
        "enterprise_skill_sync",
    }
)

REMOVED_NATIVE_TOOLS = frozenset(
    {
        "get_flow_stack",
        "create_flow_stack",
        "edit_flow_stack",
        "delete_flow_stack",
    }
)


def feature_available(feature: str) -> bool:
    """Return whether a product feature is included in this edition."""
    return feature not in REMOVED_FEATURES
