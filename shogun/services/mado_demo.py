"""Canonical Order 12 Mado hardening acceptance demo."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shogun.config import PROJECT_ROOT
from shogun.services import mado_service
from shogun.services.mado_hardening import governed_action, observe_page


async def run_mado_hardening_demo(session_id: str, profile_name: str) -> dict[str, Any]:
    portal = (Path(PROJECT_ROOT) / "shogun" / "resources" / "mado_demo_portal.html").resolve()
    url = portal.as_uri()
    steps: list[dict[str, Any]] = []

    async def run(name: str, action_type: str, operation, verification: dict | None = None) -> bool:
        result = await governed_action(
            session_id,
            action_type,
            operation,
            detail={"demo": "mado_hardening", "step": name},
            verification=verification,
        )
        steps.append({"name": name, "result": result})
        return result.get("status") != "error" and result.get("verification", {}).get("passed", True)

    if not await run(
        "Open test portal",
        "mado.navigation.open_url",
        lambda: mado_service.navigate(session_id, url),
        {"verification_type": "title_contains", "expected": "Mado Test Portal"},
    ):
        return {"success": False, "steps": steps}
    if not await run(
        "Fill approved login form",
        "mado.form.fill",
        lambda: mado_service.fill_form(
            session_id,
            [
                {"selector": "#email", "value": "demo@shogun.local"},
                {"selector": "#password", "value": "demo-only-not-a-secret"},
            ],
        ),
    ):
        return {"success": False, "steps": steps}
    if not await run(
        "Submit portal login",
        "mado.action.click",
        lambda: mado_service.click_element(session_id, "#login-button"),
        {"verification_type": "text_contains", "expected": "Portal ready"},
    ):
        return {"success": False, "steps": steps}
    if not await run(
        "Download report",
        "mado.download.file",
        lambda: mado_service.download_file(session_id, profile_name, "#download-report"),
        {"verification_type": "file_downloaded", "expected": "mado_demo_report*.csv"},
    ):
        return {"success": False, "steps": steps}
    screenshot = await mado_service.screenshot(session_id, full_page=True)
    observation = await observe_page(session_id, screenshot=False)
    steps.append({"name": "Capture final evidence", "result": {"screenshot": screenshot, "observation": observation}})
    return {
        "success": True,
        "summary": (
            "Mado opened the portal, completed the form, downloaded and verified the report, and captured evidence."
        ),
        "steps": steps,
        "screenshot": screenshot,
        "observation_artifact": observation.get("artifact"),
    }
