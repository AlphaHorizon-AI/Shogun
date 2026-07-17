"""Canonical Word Hello World acceptance workflow."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from shogun.ronin.core.ronin_controller import get_controller
from shogun.ronin.policies.ronin_policy_schema import RoninAction, RoninActionStatus


async def run_word_hello_world(*, output_path: str | None = None, agent_id: str = "operator") -> dict[str, Any]:
    """Open Word, type Hello World, save, verify, and capture final evidence."""
    target = Path(output_path).expanduser() if output_path else Path.home() / "Desktop" / "hello_world.docx"
    controller = get_controller()
    steps = [
        RoninAction(
            agent_id=agent_id,
            action_type="os.app_launch",
            target="winword.exe",
            reason="Canonical Word acceptance demo",
        ),
        RoninAction(agent_id=agent_id, action_type="os.wait_for_window", target="Word", metadata={"timeout": 30}),
        RoninAction(agent_id=agent_id, action_type="desktop.type", value="Hello World"),
        RoninAction(agent_id=agent_id, action_type="desktop.hotkey", value="ctrl+shift+s"),
        RoninAction(agent_id=agent_id, action_type="os.wait_for_window", target="Save As", metadata={"timeout": 20}),
        RoninAction(agent_id=agent_id, action_type="desktop.type", value=str(target)),
        RoninAction(agent_id=agent_id, action_type="desktop.hotkey", value="enter"),
        RoninAction(agent_id=agent_id, action_type="os.wait_for_file", target=str(target), metadata={"timeout": 30}),
        RoninAction(agent_id=agent_id, action_type="desktop.screenshot"),
    ]
    results: list[dict[str, Any]] = []
    for step in steps:
        result = await controller.execute(step)
        results.append(result.model_dump(mode="json"))
        if result.status != RoninActionStatus.SUCCESS or not result.verified:
            return {"success": False, "output_path": str(target), "failed_step": step.action_type, "results": results}
    return {
        "success": target.exists(),
        "output_path": str(target),
        "verified": target.exists(),
        "final_screenshot": results[-1].get("result_data", {}).get("screenshot_path"),
        "results": results,
    }
