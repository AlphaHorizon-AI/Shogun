"""Bare-bones AgentFlow edition metadata.

Retains Yellow Label release identity so existing Shogun Yellow Label
installations can upgrade cleanly in-place while preserving user data,
workspace folders, and AgentFlows.
"""

from __future__ import annotations

EDITION_NAME = "yellow-label"


def feature_available(feature: str) -> bool:
    """All AgentFlow capabilities are available in this edition."""
    return True
