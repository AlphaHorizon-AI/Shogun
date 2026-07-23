"""Gensui Membership Client — connects a Shogun instance to a Gensui server.

This service handles:
- Enrollment (sign-up to Gensui)
- Heartbeat (periodic status reporting)
- Policy sync (fetch effective posture)
- Command polling (check for pending commands)
- Telemetry push (send events to Gensui)
- Local policy cache (survive disconnects)
"""

from __future__ import annotations

import asyncio
import json
import logging
import platform
from datetime import datetime, timezone
from pathlib import Path

import httpx

log = logging.getLogger("shogun.gensui_client")


class GensuiClient:
    """Manages the connection between a Shogun instance and a Gensui server."""

    def __init__(self):
        from shogun.config import settings
        self.enabled = getattr(settings, "gensui_enabled", False)
        self.server_url = getattr(settings, "gensui_server_url", "http://localhost:8787").rstrip("/")
        self.enrollment_token = getattr(settings, "gensui_enrollment_token", None)
        self.instance_name = getattr(settings, "gensui_instance_name", "Shogun Instance")
        self.environment = getattr(settings, "gensui_environment", "development")
        self.heartbeat_interval = getattr(settings, "gensui_heartbeat_interval_seconds", 15)
        self.command_poll_interval = getattr(settings, "gensui_command_poll_interval_seconds", 5)
        self.policy_sync_interval = getattr(settings, "gensui_policy_sync_interval_seconds", 30)
        self.disconnect_behavior = getattr(settings, "gensui_disconnect_behavior", "CONTINUE_LAST_POLICY")
        self.telemetry_mode = getattr(settings, "gensui_telemetry_mode", "STANDARD")

        self._shogun_id: str | None = None
        self._cache_path = Path(getattr(settings, "gensui_data_path", "data")) / "gensui_membership.json"
        self._effective_posture: dict | None = None
        self._connected = False
        self._tasks: list[asyncio.Task] = []
        self._telemetry_buffer: list[dict] = []
        self._http: httpx.AsyncClient | None = None

        # Load cached state
        self._load_cache()

    # ── Cache Management ─────────────────────────────────────

    def _load_cache(self):
        """Load cached membership state from disk."""
        try:
            if self._cache_path.exists():
                data = json.loads(self._cache_path.read_text())
                self._shogun_id = data.get("shogun_id")
                self._effective_posture = data.get("effective_posture")
                self._apply_toolgate_overrides()
                log.info("[GensuiClient] Loaded cached membership: %s", self._shogun_id)
        except Exception as e:
            log.warning("[GensuiClient] Failed to load cache: %s", e)

    def _apply_toolgate_overrides(self) -> None:
        """Apply overrides from the effective posture, including cached offline policy."""
        overrides = (self._effective_posture or {}).get("tool_overrides")
        if not isinstance(overrides, dict):
            return
        try:
            from shogun.services.tool_gate import apply_gensui_overrides

            apply_gensui_overrides(overrides)
        except Exception as e:
            log.warning("[GensuiClient] Failed to apply tool overrides: %s", e)

    def _save_cache(self):
        """Save membership state to disk."""
        try:
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "shogun_id": self._shogun_id,
                "effective_posture": self._effective_posture,
                "last_sync_at": datetime.now(timezone.utc).isoformat(),
                "server_url": self.server_url,
                "disconnect_behavior": self.disconnect_behavior,
            }
            self._cache_path.write_text(json.dumps(data, indent=2))
        except Exception as e:
            log.warning("[GensuiClient] Failed to save cache: %s", e)

    # ── HTTP Client ──────────────────────────────────────────

    def _get_client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            headers = {}
            if self._shogun_id:
                headers["X-Shogun-Id"] = self._shogun_id
            self._http = httpx.AsyncClient(
                base_url=self.server_url,
                headers=headers,
                timeout=10.0,
            )
        return self._http

    async def _request(self, method: str, path: str, **kwargs) -> dict | None:
        """Make an HTTP request to the Gensui server."""
        try:
            client = self._get_client()
            if self._shogun_id:
                client.headers["X-Shogun-Id"] = self._shogun_id
            response = await client.request(method, path, **kwargs)
            if response.status_code < 400:
                self._connected = True
                return response.json()
            else:
                log.warning("[GensuiClient] %s %s returned %d", method, path, response.status_code)
                return None
        except Exception as e:
            if self._connected:
                log.warning("[GensuiClient] Connection lost to Gensui: %s", e)
                self._connected = False
                self._handle_disconnect()
            return None

    # ── Enrollment ───────────────────────────────────────────

    async def enroll(self) -> bool:
        """Attempt to enroll this Shogun with the Gensui server."""
        if not self.enrollment_token:
            log.warning("[GensuiClient] No enrollment token configured")
            return False

        result = await self._request("POST", "/api/gensui/enrollment/enroll", json={
            "token": self.enrollment_token,
            "instance_name": self.instance_name,
            "hostname": platform.node(),
            "environment": self.environment,
            "local_os": f"{platform.system()} {platform.release()}",
            "deployment_type": "desktop",
            "version": "1.3.2",
        })

        if result and result.get("shogun_id"):
            self._shogun_id = result["shogun_id"]
            self._save_cache()
            log.info("[GensuiClient] Enrolled successfully: %s (status: %s)",
                     self._shogun_id, result.get("enrollment_status"))
            return True
        return False

    # ── Heartbeat ────────────────────────────────────────────

    async def _heartbeat_loop(self):
        """Send periodic heartbeats to the Gensui server."""
        while True:
            try:
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("[GensuiClient] Heartbeat error: %s", e)
            await asyncio.sleep(self.heartbeat_interval)

    async def _send_heartbeat(self):
        """Send a single heartbeat."""
        if not self._shogun_id:
            return

        # Gather local stats
        samurai_count = 0
        workflow_count = 0
        mado_sessions = 0
        try:
            from sqlalchemy import func, select

            from shogun.db.engine import async_session_factory
            from shogun.db.models.agent import Agent
            async with async_session_factory() as db:
                result = await db.execute(
                    select(func.count()).select_from(Agent).where(
                        Agent.agent_type == "samurai",
                        Agent.status.in_(["active", "idle", "running"]),
                        Agent.is_deleted.is_(False),
                    )
                )
                samurai_count = result.scalar() or 0
        except Exception:
            pass

        # Gather external agents from Nexus Gateway
        external_agents = []
        try:
            from sqlalchemy import select

            from shogun.db.engine import async_session_factory
            from shogun.db.models.nexus import ExternalAgentModel
            async with async_session_factory() as db:
                result = await db.execute(
                    select(ExternalAgentModel).where(
                        ExternalAgentModel.is_active.is_(True),
                        ExternalAgentModel.is_deleted.is_(False),
                    )
                )
                for agent in result.scalars().all():
                    external_agents.append({
                        "id": str(agent.id),
                        "name": agent.name,
                        "platform": agent.platform,
                        "direction": agent.direction,
                        "has_endpoint": bool(agent.endpoint_url),
                    })
        except Exception:
            pass

        result = await self._request("POST", "/api/gensui/heartbeat", json={
            "shogun_id": self._shogun_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "online",
            "version": "1.3.2",
            "harakiri_state": "none",
            "active_samurai_count": samurai_count,
            "active_workflow_count": workflow_count,
            "active_mado_sessions": mado_sessions,
            "external_agents": external_agents,
            "health": {
                "archives": "healthy",
                "mado": "healthy",
                "nexus": "healthy",
                "agent_flow": "healthy",
            },
        })

        if result and result.get("effective_posture"):
            self._effective_posture = result["effective_posture"]
            self._apply_toolgate_overrides()
            self._save_cache()

    # ── Policy Sync ──────────────────────────────────────────

    async def _policy_sync_loop(self):
        """Periodically fetch effective posture from Gensui."""
        while True:
            try:
                await self._sync_policy()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("[GensuiClient] Policy sync error: %s", e)
            await asyncio.sleep(self.policy_sync_interval)

    async def _sync_policy(self):
        """Fetch the effective posture from Gensui and apply tool overrides."""
        if not self._shogun_id:
            return
        result = await self._request("GET", f"/api/gensui/policy/effective/{self._shogun_id}")
        if result:
            self._effective_posture = result
            self._apply_toolgate_overrides()
            self._save_cache()

            # ── Apply Gensui tool overrides to local ToolGate ──
    # ── Command Polling ──────────────────────────────────────

    async def _command_poll_loop(self):
        """Poll for pending commands from Gensui."""
        while True:
            try:
                await self._poll_commands()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("[GensuiClient] Command poll error: %s", e)
            await asyncio.sleep(self.command_poll_interval)

    async def _poll_commands(self):
        """Check for and execute pending commands."""
        if not self._shogun_id:
            return
        result = await self._request("GET", f"/api/gensui/commands/{self._shogun_id}")
        if result and isinstance(result, list):
            for cmd in result:
                await self._execute_command(cmd)

    async def _execute_command(self, cmd: dict):
        """Execute a command from Gensui."""
        cmd_id = cmd.get("id")
        cmd_type = cmd.get("command_type")
        payload = cmd.get("payload", {})

        log.info("[GensuiClient] Executing command: %s (%s)", cmd_type, cmd_id)

        # Acknowledge
        await self._request("POST", f"/api/gensui/commands/{cmd_id}/ack")

        try:
            if cmd_type == "harakiri":
                await self._execute_harakiri(payload)
            elif cmd_type == "posture_update":
                await self._sync_policy()
            else:
                log.warning("[GensuiClient] Unknown command type: %s", cmd_type)

            # Report success
            await self._request("POST", f"/api/gensui/commands/{cmd_id}/result", json={
                "result": {"status": "completed"},
            })
        except Exception as e:
            await self._request("POST", f"/api/gensui/commands/{cmd_id}/result", json={
                "error": str(e),
            })

    async def _execute_harakiri(self, payload: dict):
        """Execute a Harakiri command locally."""
        mode = payload.get("mode", "soft_freeze")
        event_id = payload.get("harakiri_event_id")

        log.critical("[GensuiClient] HARAKIRI EXECUTING — mode: %s", mode)

        # Activate the local kill switch
        try:
            from sqlalchemy import select

            from shogun.db.engine import async_session_factory
            from shogun.db.models.security_policy import SecurityPolicy

            async with async_session_factory() as db:
                result = await db.execute(select(SecurityPolicy))
                policy = result.scalars().first()
                if policy:
                    policy.kill_switch_active = True
                    await db.commit()
        except Exception as e:
            log.error("[GensuiClient] Failed to activate local kill switch: %s", e)

        # Acknowledge to Gensui
        if event_id:
            await self._request("POST", f"/api/gensui/harakiri/acknowledge/{event_id}")

    # ── Telemetry ────────────────────────────────────────────

    def buffer_telemetry(self, event: dict):
        """Buffer a telemetry event for batch submission."""
        if self.telemetry_mode == "MINIMAL":
            # Only buffer critical events
            if event.get("severity") not in ("error", "critical", "warn"):
                return
        self._telemetry_buffer.append(event)
        if len(self._telemetry_buffer) >= 50:
            asyncio.ensure_future(self._flush_telemetry())

    async def _telemetry_push_loop(self):
        """Periodically flush telemetry buffer."""
        while True:
            try:
                await self._flush_telemetry()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("[GensuiClient] Telemetry push error: %s", e)
            await asyncio.sleep(10)

    async def _flush_telemetry(self):
        """Send buffered telemetry events to Gensui."""
        if not self._shogun_id or not self._telemetry_buffer:
            return
        batch = self._telemetry_buffer[:100]
        self._telemetry_buffer = self._telemetry_buffer[100:]
        await self._request("POST", "/api/gensui/telemetry", json={"events": batch})

    # ── Disconnect Handling ──────────────────────────────────

    def _handle_disconnect(self):
        """Apply disconnect behavior when Gensui connection is lost."""
        log.warning("[GensuiClient] Applying disconnect behavior: %s", self.disconnect_behavior)
        # The posture guard will check the cached posture
        # More aggressive behaviors can be implemented here

    # ── Lifecycle ────────────────────────────────────────────

    async def start(self):
        """Start the Gensui client background tasks."""
        if not self.enabled:
            log.info("[GensuiClient] Gensui integration disabled")
            return

        log.info("[GensuiClient] Starting Gensui client → %s", self.server_url)

        # Enroll if not already enrolled
        if not self._shogun_id and self.enrollment_token:
            await self.enroll()

        if not self._shogun_id:
            log.warning("[GensuiClient] Not enrolled — background tasks will not start")
            return

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._heartbeat_loop()),
            asyncio.create_task(self._policy_sync_loop()),
            asyncio.create_task(self._command_poll_loop()),
            asyncio.create_task(self._telemetry_push_loop()),
        ]
        log.info("[GensuiClient] Background tasks started (heartbeat, policy sync, commands, telemetry)")

    async def stop(self):
        """Stop all background tasks."""
        for task in self._tasks:
            task.cancel()
        if self._http and not self._http.is_closed:
            await self._http.aclose()
        log.info("[GensuiClient] Stopped")

    # ── Public API ───────────────────────────────────────────

    def get_effective_posture(self) -> dict | None:
        """Get the current effective posture (from cache)."""
        return self._effective_posture

    def is_action_allowed(self, action_type: str) -> bool:
        """Check if an action is allowed under the current posture."""
        if not self.enabled or not self._effective_posture:
            return True  # No Gensui = no restrictions

        rules = self._effective_posture.get("rules", {})
        action_map = {
            "MODEL_CALL": "allow_external_models",
            "LOCAL_MODEL_CALL": "allow_local_models",
            "TOOL_EXECUTION": "allow_tool_execution",
            "MADO_SESSION": "allow_mado",
            "MADO_NAVIGATION": "allow_mado",
            "RONIN_SESSION": "allow_ronin",
            "RONIN_ACTION": "allow_ronin",
            "MEMORY_WRITE": "allow_memory_write",
            "MEMORY_READ": "allow_memory_read",
            "AGENT_FLOW": "allow_agent_flow",
            "NEXUS_MESSAGE": "allow_nexus",
            "SAMURAI_DELEGATION": "allow_samurai_delegation",
            "SCHEDULED_TRIGGER": "allow_scheduled_triggers",
            "AUTONOMOUS_LOOP": "allow_autonomous_loops",
            "EXTERNAL_WEB": "allow_external_web",
            "FILE_WRITE": "allow_file_write",
            "EXTERNAL_API": "allow_external_api",
        }

        rule_key = action_map.get(action_type)
        if rule_key is None:
            return True

        return rules.get(rule_key, True)

    @property
    def is_enrolled(self) -> bool:
        return self._shogun_id is not None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def shogun_id(self) -> str | None:
        return self._shogun_id


# Singleton instance
gensui_client = GensuiClient()
