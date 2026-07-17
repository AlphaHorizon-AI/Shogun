"""Safe retry and pause policy for Ronin desktop failures."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class RecoveryDecision:
    retry: bool
    pause: bool
    reason: str


class DesktopRecoveryService:
    def decide(
        self, *, attempt: int, max_retries: int, error: str | None, unknown_dialog: bool = False
    ) -> RecoveryDecision:
        if unknown_dialog:
            return RecoveryDecision(False, True, "Unknown or protected dialog detected; operator input required")
        if attempt < max_retries:
            return RecoveryDecision(True, False, error or "Verification failed")
        return RecoveryDecision(False, True, error or "Retry limit reached")


_recovery = DesktopRecoveryService()


def get_recovery_service() -> DesktopRecoveryService:
    return _recovery
