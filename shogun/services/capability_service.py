"""Product-capability guard for the Yellow Label edition.

Centralises capability checks so that both API endpoints and internal
services can verify whether a feature is available without scattering
edition-specific conditionals throughout the codebase.

Capabilities are resolved from two sources:

1. **Edition boundary** — hardcoded in ``edition.py`` (features that are
   permanently removed from the Yellow Label codebase).
2. **Feature flags** — runtime-configurable flags for capabilities that
   exist in the code but may be disabled by policy.

Enterprise / Gensui capabilities are always disabled in Yellow Label.
"""

from __future__ import annotations

import logging
from typing import ClassVar

from shogun.edition import REMOVED_FEATURES

logger = logging.getLogger(__name__)


class CapabilityUnavailable(Exception):  # noqa: N818 - public capability exception name
    """Raised when a requested capability is not available in this edition."""

    def __init__(self, capability: str, edition: str = "yellow_label"):
        self.capability = capability
        self.edition = edition
        super().__init__(
            f"Capability '{capability}' is not available in the {edition} edition."
        )


# Default feature-flag state for Yellow Label.
# These can be overridden via setup config later.
_DEFAULT_FLAGS: dict[str, bool] = {
    # ── SkillOpt Lab (enabled) ───────────────────────────────
    "skillopt.lab": True,
    "skillopt.regression": True,
    "skillopt.local_versions": True,
    "skillopt.local_benchmark": True,
    "skillopt.runtime_learning": True,
    "skillopt.local_rollback": True,
    "skillopt.dataset_export": True,
    # ── Gensui / Enterprise (permanently disabled) ───────────
    "gensui.skill_repository": False,
    "gensui.skill_publication": False,
    "gensui.skill_distribution": False,
    "gensui.enterprise_competence": False,
    "enterprise.skill_sync": False,
}


class CapabilityService:
    """Singleton-style capability checker.

    Usage::

        caps = CapabilityService()

        if not caps.enabled("skillopt.lab"):
            raise CapabilityUnavailable("skillopt.lab")

        # or use the convenience guard:
        caps.require("gensui.skill_publication")  # raises if disabled
    """

    _instance: ClassVar[CapabilityService | None] = None
    _flags: dict[str, bool]

    def __init__(self) -> None:
        self._flags = dict(_DEFAULT_FLAGS)

    @classmethod
    def get(cls) -> CapabilityService:
        """Return the singleton instance, creating it on first access."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── Query ────────────────────────────────────────────────

    def enabled(self, capability: str) -> bool:
        """Return whether *capability* is available in this edition."""
        # Check the hardcoded edition boundary first.
        # The REMOVED_FEATURES set uses short names (e.g. "gensui"),
        # so we check both the full dotted name and the prefix.
        prefix = capability.split(".")[0]
        if prefix in REMOVED_FEATURES or capability in REMOVED_FEATURES:
            return False

        return self._flags.get(capability, False)

    def require(self, capability: str) -> None:
        """Raise :class:`CapabilityUnavailable` if *capability* is disabled."""
        if not self.enabled(capability):
            raise CapabilityUnavailable(capability)

    # ── Mutation (for future config-driven overrides) ────────

    def set_flag(self, capability: str, enabled: bool) -> None:
        """Override a feature flag at runtime (e.g. from setup config)."""
        self._flags[capability] = enabled
        logger.info(
            "Capability flag '%s' set to %s", capability, enabled
        )

    def get_all_flags(self) -> dict[str, bool]:
        """Return a snapshot of all known capability flags."""
        return dict(self._flags)
