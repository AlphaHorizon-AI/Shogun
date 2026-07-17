"""Verification primitives used after every governed desktop action."""

from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from shogun.ronin.adapters.base_adapter import get_adapter


@dataclass(slots=True)
class VerificationResult:
    passed: bool
    check: str
    message: str
    evidence: dict[str, Any]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class DesktopVerificationService:
    async def verify(
        self,
        action_type: str,
        result_data: dict[str, Any],
        before: dict[str, Any],
        after: dict[str, Any],
        expected: dict[str, Any] | None = None,
    ) -> VerificationResult:
        expected = expected or {}
        if expected.get("file_exists"):
            path = Path(str(expected["file_exists"])).expanduser()
            return VerificationResult(
                path.exists(),
                "file_exists",
                f"File {'found' if path.exists() else 'not found'}: {path}",
                {"path": str(path)},
            )

        expected_window = expected.get("window_title") or result_data.get("expected_window")
        if expected_window:
            active = (after.get("active_window") or {}).get("title", "")
            passed = str(expected_window).lower() in str(active).lower()
            return VerificationResult(
                passed,
                "active_window",
                f"Active window: {active or 'none'}",
                {"expected": expected_window, "actual": active},
            )

        if action_type == "desktop.screenshot":
            path = result_data.get("screenshot_path")
            passed = bool(path and Path(path).exists())
            return VerificationResult(
                passed,
                "screenshot_exists",
                "Screenshot artifact created" if passed else "Screenshot artifact missing",
                {"path": path},
            )

        if action_type.startswith(("desktop.", "os.")):
            before_window = (before.get("active_window") or {}).get("title")
            after_window = (after.get("active_window") or {}).get("title")
            return VerificationResult(
                True,
                "action_completed",
                "Action completed and desktop state was observed",
                {"before_window": before_window, "after_window": after_window},
            )

        return VerificationResult(True, "result_status", "Action returned successfully", {})

    async def wait_for_window(self, title: str, *, timeout: float = 30.0, interval: float = 0.25) -> VerificationResult:
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            adapter = get_adapter()
            windows = adapter.list_windows() if adapter else []
            match = next((w for w in windows if title.lower() in str(w.get("title", "")).lower()), None)
            if match:
                return VerificationResult(
                    True, "wait_for_window", f"Window detected: {match.get('title')}", {"window": match}
                )
            await asyncio.sleep(interval)
        return VerificationResult(
            False, "wait_for_window", f"Timed out waiting for window: {title}", {"timeout": timeout}
        )

    async def wait_for_file(self, path: str, *, timeout: float = 30.0, interval: float = 0.25) -> VerificationResult:
        target = Path(path).expanduser()
        deadline = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < deadline:
            if target.exists():
                return VerificationResult(True, "wait_for_file", f"File detected: {target}", {"path": str(target)})
            await asyncio.sleep(interval)
        return VerificationResult(False, "wait_for_file", f"Timed out waiting for file: {target}", {"timeout": timeout})


_verifier = DesktopVerificationService()


def get_verifier() -> DesktopVerificationService:
    return _verifier
