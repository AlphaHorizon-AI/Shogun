"""Gensui Connection Configuration API — manage the Gensui fleet management link."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger(__name__)
router = APIRouter(prefix="/gensui", tags=["gensui-config"])

# ── Persistence ──────────────────────────────────────────────

_CONFIG_PATH = Path("data/gensui_connection.json")


def _load_config() -> dict:
    """Load persisted Gensui connection settings."""
    try:
        if _CONFIG_PATH.exists():
            return json.loads(_CONFIG_PATH.read_text())
    except Exception:
        pass
    return {}


def _save_config(data: dict) -> None:
    """Persist Gensui connection settings."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(data, indent=2))


# ── Request / Response Models ────────────────────────────────

class ConnectRequest(BaseModel):
    server_url: str
    enrollment_token: str | None = None
    instance_name: str | None = None
    environment: str = "development"


class TestRequest(BaseModel):
    server_url: str


# ── Endpoints ────────────────────────────────────────────────

@router.get("/status")
async def get_gensui_status():
    """Return current Gensui connection state."""
    config = _load_config()

    # Get live client status
    client_status = _get_client_status()

    return {
        "enabled": config.get("enabled", False),
        "server_url": config.get("server_url", ""),
        "instance_name": config.get("instance_name", ""),
        "environment": config.get("environment", "development"),
        "enrolled": client_status.get("enrolled", False),
        "connected": client_status.get("connected", False),
        "shogun_id": client_status.get("shogun_id"),
        "effective_posture": client_status.get("effective_posture"),
        "last_sync_at": client_status.get("last_sync_at"),
    }


@router.post("/connect")
async def connect_to_gensui(req: ConnectRequest):
    """Configure and connect to a Gensui server."""
    server_url = req.server_url.rstrip("/")

    # Test connectivity first
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{server_url}/api/gensui/health")
            if resp.status_code != 200:
                raise HTTPException(400, f"Gensui server returned {resp.status_code}")
    except httpx.ConnectError:
        raise HTTPException(400, "Cannot reach Gensui server at the specified URL")
    except httpx.TimeoutException:
        raise HTTPException(400, "Connection to Gensui server timed out")

    # Persist settings
    config = {
        "enabled": True,
        "server_url": server_url,
        "enrollment_token": req.enrollment_token,
        "instance_name": req.instance_name or "Shogun Instance",
        "environment": req.environment,
    }
    _save_config(config)

    # Reconfigure and start the client
    result = await _reconfigure_client(config)

    return {
        "status": "connected",
        "enrolled": result.get("enrolled", False),
        "shogun_id": result.get("shogun_id"),
        "message": "Connected to Gensui" + (
            " — enrollment pending approval" if result.get("enrollment_status") == "pending"
            else " — enrolled and active" if result.get("enrolled")
            else ""
        ),
    }


@router.post("/disconnect")
async def disconnect_from_gensui():
    """Disconnect from Gensui and clear settings."""
    # Stop the client
    try:
        from shogun.services.gensui_client import gensui_client
        await gensui_client.stop()
        gensui_client.enabled = False
        gensui_client._connected = False
        gensui_client._shogun_id = None
        gensui_client._effective_posture = None
        from shogun.services.tool_gate import (
            apply_gensui_advanced_controls,
            apply_gensui_overrides,
        )

        apply_gensui_overrides({})
        apply_gensui_advanced_controls({})
    except Exception as e:
        log.warning("Error stopping Gensui client: %s", e)

    # Clear persisted config
    config = _load_config()
    config["enabled"] = False
    _save_config(config)

    # Clear cached membership
    cache_path = Path("data/gensui_membership.json")
    if cache_path.exists():
        cache_path.unlink()

    return {"status": "disconnected", "message": "Disconnected from Gensui"}


@router.post("/test")
async def test_gensui_connection(req: TestRequest):
    """Test connectivity to a Gensui server without enrolling."""
    server_url = req.server_url.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{server_url}/api/gensui/health")
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "reachable": True,
                    "service": data.get("service", "unknown"),
                    "version": data.get("version", "unknown"),
                }
            else:
                return {"reachable": False, "error": f"Server returned {resp.status_code}"}
    except httpx.ConnectError:
        return {"reachable": False, "error": "Connection refused — is Gensui running?"}
    except httpx.TimeoutException:
        return {"reachable": False, "error": "Connection timed out"}
    except Exception as e:
        return {"reachable": False, "error": str(e)}


# ── Internal Helpers ─────────────────────────────────────────

def _get_client_status() -> dict:
    """Get live status from the GensuiClient singleton."""
    try:
        from shogun.services.gensui_client import gensui_client
        cache_path = Path("data/gensui_membership.json")
        last_sync = None
        if cache_path.exists():
            try:
                cache_data = json.loads(cache_path.read_text())
                last_sync = cache_data.get("last_sync_at")
            except Exception:
                pass

        return {
            "enrolled": gensui_client.is_enrolled,
            "connected": gensui_client.is_connected,
            "shogun_id": gensui_client.shogun_id,
            "effective_posture": gensui_client.get_effective_posture(),
            "last_sync_at": last_sync,
        }
    except Exception:
        return {}


async def _reconfigure_client(config: dict) -> dict:
    """Reconfigure and restart the GensuiClient with new settings."""
    try:
        from shogun.services.gensui_client import gensui_client

        # Stop existing tasks
        await gensui_client.stop()

        # Apply new settings
        gensui_client.enabled = True
        gensui_client.server_url = config["server_url"]
        gensui_client.enrollment_token = config.get("enrollment_token")
        gensui_client.instance_name = config.get("instance_name", "Shogun Instance")
        gensui_client.environment = config.get("environment", "development")
        gensui_client._connected = False
        gensui_client._http = None  # Force new HTTP client

        # Attempt enrollment if we have a token and aren't already enrolled
        enrolled = False
        enrollment_status = None
        if config.get("enrollment_token") and not gensui_client.is_enrolled:
            enrolled = await gensui_client.enroll()
            enrollment_status = "pending" if enrolled else None

        # Start background tasks
        await gensui_client.start()

        return {
            "enrolled": gensui_client.is_enrolled,
            "shogun_id": gensui_client.shogun_id,
            "enrollment_status": enrollment_status,
        }
    except Exception as e:
        log.error("Failed to reconfigure Gensui client: %s", e)
        return {"enrolled": False, "error": str(e)}
