"""Gensui Publisher — publishes Ronin node state to Gensui for fleet visibility.

Every Ronin node publishes on the Gensui heartbeat interval:
  hostname, machine_id, OS, environment_type, posture, active sessions,
  current app, current action, komainu status, etc.

This creates the AFM fleet view in Gensui.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger("shogun.ronin.telemetry.gensui")


async def publish_node_state() -> None:
    """Publish the current Ronin node state to Gensui."""
    from shogun.edition import feature_available

    if not feature_available("gensui"):
        return
    try:
        from shogun.config import settings
        if not settings.gensui_enabled:
            return

        from shogun.ronin.core.ronin_controller import get_controller
        from shogun.ronin.core.komainu import get_status as get_komainu_status

        controller = get_controller()
        env = controller.get_environment()

        node_state = {
            "node_type": "ronin",
            "hostname": env.hostname if env else None,
            "machine_id": env.machine_id if env else None,
            "os": env.os_type if env else None,
            "os_version": env.os_version if env else None,
            "environment_type": env.environment_type.value if env else None,
            "komainu_status": get_komainu_status().get("status", "inactive"),
        }

        # Publish via Gensui client
        try:
            from shogun.services.gensui_client import gensui_client
            await gensui_client.publish_telemetry("ronin_node", node_state)
        except Exception as exc:
            log.debug("Ronin: Gensui publish failed: %s", exc)

    except Exception as exc:
        log.debug("Ronin: node state collection failed: %s", exc)


async def publish_action(action_type: str, status: str, current_app: str | None = None) -> None:
    """Publish a Ronin action event to Gensui."""
    from shogun.edition import feature_available

    if not feature_available("gensui"):
        return
    try:
        from shogun.config import settings
        if not settings.gensui_enabled:
            return

        from shogun.services.gensui_client import gensui_client
        await gensui_client.publish_telemetry("ronin_action", {
            "action_type": action_type,
            "status": status,
            "current_app": current_app,
        })
    except Exception:
        pass
