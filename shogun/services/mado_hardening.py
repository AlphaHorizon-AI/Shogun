"""Governed reliability layer for Mado browser automation.

This module intentionally wraps the existing Playwright service instead of
creating a second browser runtime. It owns profile isolation, runtime state,
structured observation, artifacts, verification, recovery, and audit events.
"""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import json
import mimetypes
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import HTTPException

from shogun.config import PROJECT_ROOT, settings

_SECRET_PATTERN = re.compile(r"(?i)(password|passwd|secret|token|api[_ -]?key|authorization|cookie|session[_ -]?id)")


def mado_config() -> dict[str, Any]:
    from shogun.api.setup import MADO_DEFAULTS, _read_setup

    return {**MADO_DEFAULTS, **_read_setup().get("mado", {})}


def _redact(value: Any, key: str = "") -> Any:
    if _SECRET_PATTERN.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+", r"\1[REDACTED]", value)
        value = re.sub(r"(?i)(password|secret|token|api[_ -]?key)\s*[:=]\s*\S+", r"\1=[REDACTED]", value)
    return value


async def emit_mado_event(
    event_type: str,
    action: str,
    *,
    session_id: str | None = None,
    stack_run_id: str | None = None,
    step_run_id: str | None = None,
    agent_id: str | None = None,
    result: str = "success",
    severity: str = "info",
    detail: dict[str, Any] | None = None,
) -> str:
    """Send a redacted Mado event through the central EventLogger."""
    try:
        from shogun.services.event_logger import EventLogger

        try:
            event_session_id = str(uuid.UUID(session_id)) if session_id else None
        except (ValueError, TypeError):
            event_session_id = None
        try:
            event_agent_id = str(uuid.UUID(agent_id)) if agent_id else None
        except (ValueError, TypeError):
            event_agent_id = None

        return await EventLogger.emit(
            category="mado",
            event_type=event_type,
            action=action,
            result=result,
            severity=severity,
            agent_id=event_agent_id,
            session_id=event_session_id,
            trace_id=stack_run_id,
            detail=_redact(
                {
                    "stack_run_id": stack_run_id,
                    "step_run_id": step_run_id,
                    "mado_session_id": session_id,
                    **(detail or {}),
                }
            ),
        )
    except Exception:
        return ""


@dataclass
class MadoRuntimeState:
    session_id: str
    status: str = "idle"
    profile_id: str | None = None
    posture: str | None = None
    mode: str = "headless"
    stack_run_id: str | None = None
    step_run_id: str | None = None
    agent_id: str | None = None
    current_url: str | None = None
    title: str | None = None
    last_action: str | None = None
    last_screenshot: str | None = None
    last_verification: dict[str, Any] | None = None
    last_error: str | None = None
    retry_count: int = 0
    page_load_count: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_active_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    timeline: list[dict[str, Any]] = field(default_factory=list)

    def record(self, event_type: str, message: str, **detail: Any) -> None:
        self.last_active_at = datetime.now(timezone.utc).isoformat()
        self.timeline.append(
            {"timestamp": self.last_active_at, "event_type": event_type, "message": message, **_redact(detail)}
        )
        self.timeline = self.timeline[-200:]


class MadoRuntimeRegistry:
    def __init__(self) -> None:
        self._states: dict[str, MadoRuntimeState] = {}

    def register(self, session_id: str, **metadata: Any) -> MadoRuntimeState:
        state = self._states.get(session_id) or MadoRuntimeState(session_id=session_id)
        for key, value in metadata.items():
            if value is not None and hasattr(state, key):
                setattr(state, key, str(value) if key.endswith("_id") else value)
        state.record("mado.session.created", "Browser session registered")
        self._states[session_id] = state
        return state

    def get(self, session_id: str) -> MadoRuntimeState:
        return self._states.setdefault(session_id, MadoRuntimeState(session_id=session_id))

    def list(self) -> list[dict[str, Any]]:
        return [vars(state) for state in self._states.values()]

    def pause(self, session_id: str, reason: str = "Paused by operator") -> MadoRuntimeState:
        state = self.get(session_id)
        state.status = "paused"
        state.record("mado.session.paused", reason)
        return state

    def resume(self, session_id: str) -> MadoRuntimeState:
        state = self.get(session_id)
        state.status = "active"
        state.last_error = None
        state.record("mado.session.resumed", "Browser session resumed")
        return state

    def close(self, session_id: str) -> MadoRuntimeState:
        state = self.get(session_id)
        state.status = "closed"
        state.record("mado.session.closed", "Browser session closed")
        return state

    def discard(self, session_id: str) -> MadoRuntimeState | None:
        """Forget a transient session after its durable audit events are emitted."""
        return self._states.pop(session_id, None)


runtime_registry = MadoRuntimeRegistry()


class MadoProfileManager:
    """Safe persistent-profile paths and exclusive per-profile locks."""

    def __init__(self) -> None:
        self.root = (Path(settings.mado_path) / "profiles").resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._owners: dict[str, str] = {}

    @staticmethod
    def sanitize(profile_id: str) -> str:
        sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", profile_id.strip())[:80]
        if not sanitized:
            raise HTTPException(status_code=400, detail="A valid profile name is required.")
        return sanitized

    def path_for(self, profile_id: str) -> Path:
        path = (self.root / self.sanitize(profile_id)).resolve()
        if path.parent != self.root:
            raise HTTPException(status_code=403, detail="Profile path escapes the configured Mado profile root.")
        return path

    def lock(self, profile_id: str, session_id: str) -> Path:
        profile_id = self.sanitize(profile_id)
        owner = self._owners.get(profile_id)
        if owner and owner != session_id:
            raise HTTPException(status_code=409, detail=f"Mado profile '{profile_id}' is already in use.")
        self._owners[profile_id] = session_id
        path = self.path_for(profile_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def release(self, profile_id: str, session_id: str) -> None:
        profile_id = self.sanitize(profile_id)
        if self._owners.get(profile_id) == session_id:
            self._owners.pop(profile_id, None)

    def list(self) -> list[dict[str, Any]]:
        return [
            {
                "profile_id": path.name,
                "path": str(path),
                "locked": path.name in self._owners,
                "session_id": self._owners.get(path.name),
            }
            for path in sorted(self.root.iterdir())
            if path.is_dir()
        ]


profile_manager = MadoProfileManager()


def validate_upload_path(file_path: str) -> Path:
    """Uploads are restricted to project workspace and Mado download artifacts."""
    path = Path(file_path).expanduser().resolve()
    roots = [Path(PROJECT_ROOT).resolve(), (Path(settings.mado_path) / "downloads").resolve()]
    if not path.is_file() or not any(path == root or root in path.parents for root in roots):
        raise HTTPException(status_code=403, detail="Uploads must reference an existing approved workspace file.")
    return path


def validate_download_path(path: Path) -> Path:
    root = (Path(settings.mado_path) / "downloads").resolve()
    resolved = path.resolve()
    if root not in resolved.parents:
        raise HTTPException(status_code=403, detail="Downloads must remain under the controlled Mado directory.")
    return resolved


class MadoPermissionGuard:
    async def check(
        self,
        action_type: str,
        *,
        url: str | None = None,
        mode: str | None = None,
        persistent_profile: bool = False,
    ) -> dict[str, Any]:
        from shogun.services.posture_guard import get_posture_tool_filter

        posture = await get_posture_tool_filter()
        config = mado_config()
        tier = str(posture.get("active_tier", "guarded")).lower()
        if posture.get("kill_switch_active"):
            raise HTTPException(status_code=403, detail="Mado is stopped by the Shogun kill switch.")
        if not config.get("enabled", True) or not posture.get("mado_enabled", False):
            raise HTTPException(status_code=403, detail=f"Mado is disabled at {tier.upper()} posture.")
        if mode == "visible" and (posture.get("mado_headless_only", True) or not config.get("visible_allowed", True)):
            raise HTTPException(status_code=403, detail="Visible Mado sessions are disabled by the current policy.")
        if mode == "headless" and not config.get("headless_allowed", True):
            raise HTTPException(status_code=403, detail="Headless Mado sessions are disabled by configuration.")
        if persistent_profile and not config.get("allow_persistent_profiles", False):
            raise HTTPException(status_code=403, detail="Persistent Mado profiles require explicit permission.")
        if action_type.startswith("mado.download") and not posture.get("mado_downloads_enabled", False):
            raise HTTPException(status_code=403, detail="Mado downloads are disabled by the current posture.")
        if action_type.startswith("mado.download") and config.get("allow_file_downloads") == "blocked":
            raise HTTPException(status_code=403, detail="Mado downloads are blocked by local configuration.")
        if action_type.startswith("mado.upload") and not posture.get("mado_uploads_enabled", False):
            raise HTTPException(status_code=403, detail="Mado uploads are disabled by the current posture.")
        if action_type.startswith("mado.upload") and config.get("allow_file_uploads") == "blocked":
            raise HTTPException(status_code=403, detail="Mado uploads are blocked by local configuration.")
        if action_type.startswith("mado.form") and not posture.get("mado_form_submit_enabled", False):
            raise HTTPException(status_code=403, detail="Mado form operations are disabled by the current posture.")
        if action_type.startswith("mado.form") and config.get("allow_form_submit") == "blocked":
            raise HTTPException(status_code=403, detail="Mado form operations are blocked by local configuration.")
        if url:
            effective_config = dict(config)
            effective_config["allowed_domains"] = posture.get("mado_allowed_domains") or config.get(
                "allowed_domains", []
            )
            effective_config["allow_external_urls"] = bool(
                posture.get("mado_external_urls_enabled", False) or config.get("allow_external_urls", False)
            )
            self._check_url(url, effective_config, tier)
        return {**posture, "mado_config": config}

    @staticmethod
    def _check_url(url: str, config: dict[str, Any], tier: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https", "file"}:
            raise HTTPException(status_code=403, detail=f"Mado cannot open URL scheme '{parsed.scheme}'.")
        domain = (parsed.hostname or "").lower()
        blocked = [str(item).lower() for item in config.get("blocked_domains", [])]
        if domain and any(domain == item or domain.endswith(f".{item}") for item in blocked):
            raise HTTPException(status_code=403, detail=f"Domain '{domain}' is blocked by Mado policy.")
        allowed = [str(item).lower() for item in config.get("allowed_domains", [])]
        local = domain in {"", "localhost", "127.0.0.1", "::1"}
        if not local and allowed and not any(domain == item or domain.endswith(f".{item}") for item in allowed):
            raise HTTPException(status_code=403, detail=f"Domain '{domain}' is not in the Mado allowlist.")
        if (
            not local
            and not allowed
            and not config.get("allow_external_urls", False)
            and tier in {"guarded", "tactical"}
        ):
            raise HTTPException(
                status_code=403, detail="External URLs require an allowlist or explicit Mado permission."
            )


permission_guard = MadoPermissionGuard()


class MadoArtifactService:
    def __init__(self) -> None:
        self.root = (Path(settings.mado_path) / "artifacts").resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def store_json(self, session_id: str, artifact_type: str, data: Any, **metadata: Any) -> dict[str, Any]:
        artifact_id = str(uuid.uuid4())
        session_root = (self.root / re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)).resolve()
        if self.root not in session_root.parents:
            raise ValueError("Invalid Mado artifact path")
        session_root.mkdir(parents=True, exist_ok=True)
        path = session_root / f"{artifact_id}_{artifact_type}.json"
        payload = {
            "artifact_id": artifact_id,
            "artifact_type": artifact_type,
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "metadata": _redact(metadata),
            "data": _redact(data),
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return {**payload, "path": str(path), "data": None}

    def describe_file(self, session_id: str, path: Path, artifact_type: str = "download") -> dict[str, Any]:
        path = validate_download_path(path)
        return {
            "artifact_id": str(uuid.uuid4()),
            "artifact_type": artifact_type,
            "session_id": session_id,
            "path": str(path),
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            "mime_type": mimetypes.guess_type(path.name)[0] or "application/octet-stream",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

    def list(self, session_id: str) -> list[dict[str, Any]]:
        session_root = self.root / re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)
        artifacts: list[dict[str, Any]] = []
        if session_root.exists():
            for path in sorted(session_root.glob("*.json"), reverse=True):
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    artifacts.append({**payload, "path": str(path), "data": None})
                except Exception:
                    continue
        return artifacts


artifact_service = MadoArtifactService()


async def observe_page(session_id: str, *, screenshot: bool = False, mode: str = "hybrid") -> dict[str, Any]:
    from shogun.services import mado_service

    page = mado_service._get_page(session_id)

    def _observe() -> dict[str, Any]:
        script = (Path(PROJECT_ROOT) / "shogun" / "resources" / "mado_observer.js").read_text(encoding="utf-8")
        observed = page.evaluate(script)
        return {"url": page.url, "title": page.title(), **observed}

    observed = await mado_service._run_in_pw_thread(_observe)
    observed["observation_mode"] = mode
    if screenshot:
        shot = await mado_service.screenshot(session_id, full_page=False)
        observed["screenshot"] = shot.get("path")
    state = runtime_registry.get(session_id)
    state.current_url = observed.get("url")
    state.title = observed.get("title")
    state.last_screenshot = observed.get("screenshot") or state.last_screenshot
    state.record("mado.page.observed", f"Observed {state.title or state.current_url}", mode=mode)
    artifact = artifact_service.store_json(session_id, "observation", observed, url=observed.get("url"))
    observed["artifact"] = artifact
    await emit_mado_event(
        "mado.page.observed",
        f"Observed browser page: {observed.get('title') or observed.get('url')}",
        session_id=session_id,
        stack_run_id=state.stack_run_id,
        step_run_id=state.step_run_id,
        agent_id=state.agent_id,
        detail={"url": observed.get("url"), "title": observed.get("title"), "artifact_id": artifact["artifact_id"]},
    )
    return observed


async def verify_page(session_id: str, request: dict[str, Any]) -> dict[str, Any]:
    verification_type = str(request.get("verification_type") or request.get("type") or "no_error_banner")
    expected = request.get("expected")
    await emit_mado_event("mado.verification.started", verification_type, session_id=session_id, detail=request)
    observed = await observe_page(session_id, screenshot=verification_type == "visual_state")
    passed = False
    actual: Any = None
    if verification_type == "url_matches":
        actual = observed.get("url", "")
        passed = fnmatch.fnmatch(actual, str(expected)) or str(expected) in actual
    elif verification_type == "title_contains":
        actual = observed.get("title", "")
        passed = str(expected).lower() in actual.lower()
    elif verification_type == "text_contains":
        actual = observed.get("visible_text", "")
        passed = str(expected).lower() in actual.lower()
    elif verification_type == "element_exists":
        candidates = observed.get("clickable_elements", []) + observed.get("form_fields", [])
        actual = [item.get("label") or item.get("selector") for item in candidates]
        passed = any(str(expected).lower() in str(item).lower() for item in actual)
    elif verification_type == "table_contains":
        actual = observed.get("visible_text", "")
        passed = str(expected).lower() in actual.lower() and bool(observed.get("tables"))
    elif verification_type == "no_error_banner":
        actual = observed.get("errors", [])
        passed = not actual
    elif verification_type == "file_downloaded":
        root = (Path(settings.mado_path) / "downloads").resolve()
        pattern = str(expected or "*")
        files = [item for item in root.rglob(pattern) if item.is_file() and not item.name.endswith(".crdownload")]
        actual = [str(item) for item in files]
        passed = any(item.stat().st_size > 0 for item in files)
    elif verification_type == "form_submitted":
        actual = observed.get("state_flags", {})
        passed = not actual.get("error_banner") and not actual.get("login_page")
    elif verification_type in {"visual_state", "screenshot_matches_expectation"}:
        actual = observed.get("screenshot")
        passed = bool(actual and Path(actual).exists())
    result = {
        "verification_type": verification_type,
        "expected": _redact(expected),
        "observed": _redact(actual),
        "status": "passed" if passed else "failed",
        "passed": passed,
        "artifact": artifact_service.store_json(session_id, "verification", {"request": request, "passed": passed}),
    }
    state = runtime_registry.get(session_id)
    state.last_verification = result
    state.record(f"mado.verification.{result['status']}", f"{verification_type}: {result['status']}")
    await emit_mado_event(
        f"mado.verification.{result['status']}",
        f"Mado verification {result['status']}: {verification_type}",
        session_id=session_id,
        stack_run_id=state.stack_run_id,
        step_run_id=state.step_run_id,
        agent_id=state.agent_id,
        result=result["status"],
        severity="info" if passed else "warn",
        detail=result,
    )
    return result


async def governed_action(
    session_id: str,
    action_type: str,
    operation: Callable[[], Awaitable[dict[str, Any]]],
    *,
    detail: dict[str, Any] | None = None,
    verification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute, observe, verify, retry, and audit one browser-native action."""
    state = runtime_registry.get(session_id)
    try:
        await permission_guard.check(action_type)
    except HTTPException as exc:
        state.record("mado.action.blocked", str(exc.detail), action_type=action_type)
        await emit_mado_event(
            "mado.action.blocked",
            action_type,
            session_id=session_id,
            result="blocked",
            severity="warn",
            detail={"reason": exc.detail},
        )
        raise
    config = mado_config()
    created = datetime.fromisoformat(state.created_at)
    runtime_seconds = (datetime.now(timezone.utc) - created).total_seconds()
    if runtime_seconds > int(config.get("max_runtime_seconds", 1800)):
        state.status = "paused"
        raise HTTPException(status_code=409, detail="Mado session reached its maximum configured runtime.")
    if action_type.startswith("mado.navigation"):
        state.page_load_count += 1
        if state.page_load_count > int(config.get("max_pages_per_run", 50)):
            state.status = "paused"
            raise HTTPException(status_code=409, detail="Mado session reached its maximum page limit.")
    if state.status == "paused":
        raise HTTPException(status_code=409, detail="Mado session is paused.")
    state.status = "active"
    state.last_action = action_type
    state.record("mado.action.requested", action_type)
    await emit_mado_event("mado.action.requested", action_type, session_id=session_id, detail=detail)
    await emit_mado_event("mado.action.allowed", action_type, session_id=session_id, detail=detail)
    started_event = {
        "mado.navigation.open_url": "mado.navigation.started",
        "mado.form.fill": "mado.form.detected",
        "mado.download.file": "mado.download.started",
        "mado.upload.file": "mado.upload.requested",
    }.get(action_type)
    if started_event:
        await emit_mado_event(started_event, action_type, session_id=session_id, detail=detail)
    retry_config = config.get("retry", {})
    attempts = max(1, min(int(retry_config.get("max_attempts", 3)), 5))
    backoffs = retry_config.get("backoff_seconds", [1, 3, 8])
    last_result: dict[str, Any] = {}
    for attempt in range(attempts):
        started = time.monotonic()
        try:
            last_result = await operation()
            if last_result.get("status") in {"error", "blocked", "failed"}:
                raise RuntimeError(last_result.get("error") or last_result.get("reason") or "Browser action failed")
            if verification or config.get("require_verification", True):
                verify_request = verification or {"verification_type": "no_error_banner"}
                verification_result = await verify_page(session_id, verify_request)
                last_result["verification"] = verification_result
                if not verification_result["passed"]:
                    raise RuntimeError(f"Verification failed: {verification_result['verification_type']}")
            state.retry_count = attempt
            state.last_error = None
            state.record("mado.action.completed", action_type, duration_ms=int((time.monotonic() - started) * 1000))
            await emit_mado_event(
                "mado.action.completed", action_type, session_id=session_id, result="completed", detail=last_result
            )
            if attempt:
                await emit_mado_event(
                    "mado.recovery.completed",
                    f"Recovered {action_type}",
                    session_id=session_id,
                    detail={"attempts": attempt + 1},
                )
            completed_event = {
                "mado.navigation.open_url": "mado.navigation.completed",
                "mado.form.fill": "mado.form.filled",
                "mado.download.file": "mado.download.completed",
                "mado.upload.file": "mado.upload.completed",
                "mado.page.screenshot": "mado.screenshot.captured",
            }.get(action_type)
            if completed_event:
                await emit_mado_event(
                    completed_event, action_type, session_id=session_id, result="completed", detail=last_result
                )
            return last_result
        except Exception as exc:
            state.last_error = str(exc)[:500]
            if attempt + 1 < attempts:
                state.retry_count = attempt + 1
                state.record("mado.recovery.started", str(exc), attempt=attempt + 1)
                await emit_mado_event(
                    "mado.recovery.started",
                    f"Retrying {action_type}",
                    session_id=session_id,
                    result="retrying",
                    severity="warn",
                    detail={"attempt": attempt + 1, "error": str(exc)},
                )
                await asyncio.sleep(float(backoffs[min(attempt, len(backoffs) - 1)]))
                continue
            state.status = "error"
            state.record("mado.action.failed", str(exc), action_type=action_type)
            if config.get("audit", {}).get("capture_screenshots_on_error", True):
                try:
                    from shogun.services.mado_service import screenshot

                    shot = await screenshot(session_id, full_page=False)
                    state.last_screenshot = shot.get("path")
                except Exception:
                    pass
            await emit_mado_event(
                "mado.action.failed",
                action_type,
                session_id=session_id,
                result="failed",
                severity="error",
                detail={"error": str(exc), "attempts": attempts},
            )
            failed_event = {
                "mado.navigation.open_url": "mado.navigation.failed",
                "mado.form.fill": "mado.form.validation_failed",
                "mado.download.file": "mado.download.failed",
                "mado.upload.file": "mado.upload.blocked",
            }.get(action_type)
            if failed_event:
                await emit_mado_event(
                    failed_event,
                    action_type,
                    session_id=session_id,
                    result="failed",
                    severity="warn",
                    detail={"error": str(exc)},
                )
            await emit_mado_event(
                "mado.recovery.failed",
                f"Recovery exhausted for {action_type}",
                session_id=session_id,
                result="failed",
                severity="warn",
                detail={"attempts": attempts},
            )
            return {**last_result, "status": "error", "error": str(exc)[:500], "retry_count": attempt}
    return last_result


async def kill_all_mado_sessions(reason: str = "Shogun kill switch activated") -> dict[str, Any]:
    from shogun.services.mado_service import close_all_browsers

    closed = await close_all_browsers()
    for state in runtime_registry._states.values():
        if state.status not in {"closed", "cancelled"}:
            state.status = "cancelled"
            state.record("mado.session.closed", reason)
    try:
        from sqlalchemy import update

        from shogun.db.engine import async_session_factory
        from shogun.db.models.mado_session import MadoSession

        async with async_session_factory() as session:
            await session.execute(
                update(MadoSession)
                .where(MadoSession.status.in_(["active", "paused", "idle"]))
                .values(status="cancelled")
            )
            await session.commit()
    except Exception:
        pass
    await emit_mado_event(
        "mado.kill_switch.triggered", reason, result="stopped", severity="critical", detail={"closed": closed}
    )
    return {"stopped": True, "sessions_closed": closed}
