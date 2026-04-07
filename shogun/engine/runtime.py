"""Shogun runtime — agent orchestration engine stub.

This module will contain the core runtime loop, agent lifecycle management,
and task orchestration in future phases.
"""

from __future__ import annotations


class ShogunRuntime:
    """Stub for the Shogun agent orchestration runtime."""

    def __init__(self):
        self.status = "initialized"

    async def start(self):
        self.status = "running"

    async def stop(self):
        self.status = "stopped"
