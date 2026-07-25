"""Consent, persistence, queueing, scheduling, and transport orchestration."""

from __future__ import annotations

import asyncio
import logging
import os
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from shogun.telemetry.config import (
    CONSENT_NOTICE_VERSION,
    HEARTBEAT_JITTER_SECONDS,
    HEARTBEAT_SECONDS,
    MAX_QUEUE_EVENTS,
    PRIVACY_NOTICE_URL,
    QUEUE_TTL_DAYS,
    load_config,
)
from shogun.telemetry.models import (
    EventType,
    QueuedEvent,
    RegistrationResponse,
    SubmissionResponse,
    TelemetryEvent,
    TelemetryState,
)
from shogun.telemetry.payload import build_event, build_registration
from shogun.telemetry.transport import TelemetryTransport

log = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class TelemetryService:
    """Installation-level telemetry that is inert until explicit consent."""

    def __init__(self, *, state_path: Path | None = None, endpoint: str | None = None) -> None:
        config = load_config()
        self.state_path = state_path or config.state_path
        self.transport = TelemetryTransport(endpoint or config.endpoint)
        self._task: asyncio.Task | None = None
        self._delivery_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    def _load(self) -> TelemetryState:
        try:
            state = TelemetryState.model_validate_json(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return TelemetryState()
        if state.enabled and state.consent_notice_version != CONSENT_NOTICE_VERSION:
            state.enabled = False
            state.telemetry_token = None
            state.last_result = "Consent renewal required"
        cutoff = _utcnow() - timedelta(days=QUEUE_TTL_DAYS)
        state.queue = [item for item in state.queue if item.queued_at >= cutoff][-MAX_QUEUE_EVENTS:]
        return state

    def _save(self, state: TelemetryState) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        temporary.replace(self.state_path)
        try:
            os.chmod(self.state_path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _schedule_from(now: datetime) -> datetime:
        jitter = secrets.randbelow(2 * HEARTBEAT_JITTER_SECONDS + 1) - HEARTBEAT_JITTER_SECONDS
        return now + timedelta(seconds=HEARTBEAT_SECONDS + jitter)

    def status(self) -> dict:
        state = self._load()
        identifier = str(state.installation_id) if state.installation_id else None
        return {
            "enabled": state.enabled,
            "show_first_run_prompt": not state.enabled and not state.prompt_dismissed,
            "requires_consent_renewal": (
                state.consent_notice_version not in (None, CONSENT_NOTICE_VERSION)
            ),
            "consent_notice_version": state.consent_notice_version,
            "required_consent_version": CONSENT_NOTICE_VERSION,
            "consented_at": state.consented_at,
            "installation_id_abbreviated": (
                f"{identifier[:4]}…{identifier[-4:]}" if identifier else None
            ),
            "last_sent_at": state.last_sent_at,
            "next_scheduled_at": state.next_scheduled_at,
            "last_result": state.last_result,
            "queued_events": len(state.queue),
            "privacy_notice_url": PRIVACY_NOTICE_URL,
            "shared_fields": [
                "schema_version", "event_id", "event_type", "occurred_at",
                "shogun_version", "build_id", "release_channel",
                "distribution_channel", "platform_family", "architecture",
                "install_type", "operation_mode", "consent_notice_version",
                "previous_version (updates only)",
            ],
            "never_shared": [
                "prompts or responses", "files or paths", "memory", "messages",
                "people or organization identities", "credentials", "hostnames",
                "hardware identifiers", "IP addresses as telemetry fields",
            ],
        }

    def dismiss_prompt(self) -> dict:
        state = self._load()
        state.prompt_dismissed = True
        state.last_result = state.last_result or "Telemetry invitation dismissed"
        self._save(state)
        return self.status()

    def identifier(self) -> str | None:
        state = self._load()
        return str(state.installation_id) if state.installation_id else None

    def preview(self, event_type: EventType = EventType.ACTIVE_HEARTBEAT) -> dict:
        state = self._load()
        notice = state.consent_notice_version or CONSENT_NOTICE_VERSION
        payload = build_event(event_type, notice_version=notice).model_dump(
            mode="json", exclude_none=True
        )
        payload["event_id"] = "generated-at-send-time"
        payload["occurred_at"] = "generated-at-send-time"
        return {
            "payload": payload,
            "notice": (
                "The installation identifier and authentication token are transmitted "
                "during registration/authentication but are hidden from this screen."
            ),
        }

    async def enable(
        self, notice_version: str, *, actor: str, register_immediately: bool = True
    ) -> dict:
        if notice_version != CONSENT_NOTICE_VERSION:
            raise ValueError(f"Consent notice version {CONSENT_NOTICE_VERSION} must be accepted")
        async with self._lock:
            state = self._load()
            if not state.installation_id:
                state.installation_id = uuid4()
            if not state.instance_nonce:
                state.instance_nonce = uuid4()
            state.enabled = True
            state.prompt_dismissed = True
            state.consent_notice_version = notice_version
            state.consented_at = _utcnow()
            state.consent_actor = (
                "primary_admin" if actor in {"token_admin", "primary_admin"} else
                "installer" if actor == "installer" else "local_administrator"
            )
            state.next_scheduled_at = self._schedule_from(_utcnow())
            state.last_result = "Consent saved; registration pending"
            self._save(state)
            if register_immediately:
                await self._register_and_flush(state)
            if register_immediately and not any(
                item.event.event_type == EventType.INSTALL_COMPLETED for item in state.queue
            ):
                await self._send_or_queue(state, build_event(
                    EventType.INSTALL_COMPLETED, notice_version=notice_version
                ))
            self._save(state)
            return self.status()

    async def _register_and_flush(
        self, state: TelemetryState, *, allow_clone_rotation: bool = True
    ) -> None:
        if not state.enabled or not state.installation_id or not state.instance_nonce:
            return
        if not state.telemetry_token:
            try:
                payload = build_registration(
                    state.installation_id,
                    state.instance_nonce,
                    state.consent_notice_version or CONSENT_NOTICE_VERSION,
                ).model_dump(mode="json")
                response = RegistrationResponse.model_validate(
                    await self.transport.post_json("/v1/installations/register", payload)
                )
                state.telemetry_token = response.telemetry_token
                state.last_result = "Registered"
                self._save(state)
            except Exception as exc:
                # A restored/cloned configuration may legitimately share the
                # old identifier. The service detects the independent nonce;
                # rotate locally without using any machine fingerprint.
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code == 409 and allow_clone_rotation:
                    state.installation_id = uuid4()
                    state.instance_nonce = uuid4()
                    state.telemetry_token = None
                    state.last_result = "Clone detected; installation identity rotated"
                    self._save(state)
                    return await self._register_and_flush(
                        state, allow_clone_rotation=False
                    )
                state.last_result = "Not sent — service unavailable"
                self._save(state)
                return
        await self._flush_queue(state)

    async def _send_event(self, state: TelemetryState, event: TelemetryEvent) -> bool:
        if not state.enabled or not state.telemetry_token:
            return False
        try:
            response = SubmissionResponse.model_validate(
                await self.transport.post_json(
                    "/v1/events",
                    {"events": [event.model_dump(mode="json", exclude_none=True)]},
                    state.telemetry_token,
                )
            )
            if response.status not in {"accepted", "duplicate"}:
                state.last_result = response.status
                return False
            state.last_sent_at = _utcnow()
            state.last_result = response.status
            if event.event_type != EventType.TELEMETRY_TEST:
                state.last_reported_version = event.shogun_version
            return True
        except Exception:
            state.last_result = "Not sent — service unavailable"
            return False

    async def _send_or_queue(self, state: TelemetryState, event: TelemetryEvent) -> bool:
        if await self._send_event(state, event):
            return True
        if event.event_type == EventType.ACTIVE_HEARTBEAT:
            state.queue = [
                item for item in state.queue
                if item.event.event_type != EventType.ACTIVE_HEARTBEAT
            ]
        if not any(item.event.event_id == event.event_id for item in state.queue):
            state.queue.append(QueuedEvent(queued_at=_utcnow(), event=event))
            state.queue = state.queue[-MAX_QUEUE_EVENTS:]
        return False

    async def _flush_queue(self, state: TelemetryState) -> None:
        original = list(state.queue)
        remaining: list[QueuedEvent] = []
        for index, item in enumerate(original):
            if not await self._send_event(state, item.event):
                remaining = original[index:]
                break
        state.queue = remaining[-MAX_QUEUE_EVENTS:]
        self._save(state)

    async def disable(self, *, delete_remote: bool = False) -> dict:
        async with self._lock:
            state = self._load()
            token = state.telemetry_token
            if state.enabled and token:
                event = build_event(
                    EventType.CONSENT_REVOKED,
                    notice_version=state.consent_notice_version or CONSENT_NOTICE_VERSION,
                )
                await self._send_event(state, event)
                if delete_remote:
                    try:
                        await self.transport.delete("/v1/installations/self", token)
                    except Exception:
                        state.last_result = "Disabled locally; remote deletion not confirmed"
            state.enabled = False
            state.telemetry_token = None
            state.next_scheduled_at = None
            state.queue = []
            state.last_result = state.last_result or "Disabled"
            self._save(state)
            return self.status()

    async def delete_remote(self) -> dict:
        return await self.disable(delete_remote=True)

    async def send_test(self) -> dict:
        async with self._lock:
            state = self._load()
            if not state.enabled:
                raise ValueError("Telemetry is disabled")
            await self._register_and_flush(state)
            sent = await self._send_event(
                state,
                build_event(
                    EventType.TELEMETRY_TEST,
                    notice_version=state.consent_notice_version or CONSENT_NOTICE_VERSION,
                ),
            )
            self._save(state)
            return {"sent": sent, "result": state.last_result}

    async def record_update(self, previous_version: str) -> None:
        async with self._lock:
            state = self._load()
            if not state.enabled or state.last_reported_version == build_event(
                EventType.UPDATE_COMPLETED,
                notice_version=state.consent_notice_version or CONSENT_NOTICE_VERSION,
            ).shogun_version:
                return
            await self._register_and_flush(state)
            await self._send_or_queue(
                state,
                build_event(
                    EventType.UPDATE_COMPLETED,
                    notice_version=state.consent_notice_version or CONSENT_NOTICE_VERSION,
                    previous_version=previous_version,
                ),
            )
            self._save(state)

    async def run_due_heartbeat(self) -> None:
        async with self._lock:
            state = self._load()
            if not state.enabled:
                return
            now = _utcnow()
            if state.next_scheduled_at and state.next_scheduled_at > now:
                return
            await self._register_and_flush(state)
            await self._send_or_queue(
                state,
                build_event(
                    EventType.ACTIVE_HEARTBEAT,
                    notice_version=state.consent_notice_version or CONSENT_NOTICE_VERSION,
                ),
            )
            state.next_scheduled_at = self._schedule_from(now)
            self._save(state)

    async def _scheduler(self) -> None:
        while True:
            try:
                await self.run_due_heartbeat()
            except Exception:
                log.debug("Installation telemetry heartbeat failed safely", exc_info=True)
            await asyncio.sleep(60 * 60)

    async def _initial_delivery(self) -> None:
        """Deliver install/update state after startup without delaying readiness."""
        async with self._lock:
            state = self._load()
            if not state.enabled:
                return
            await self._register_and_flush(state)
            current = build_event(
                EventType.INSTALL_COMPLETED,
                notice_version=state.consent_notice_version or CONSENT_NOTICE_VERSION,
            ).shogun_version
            if state.last_reported_version is None:
                event = build_event(
                    EventType.INSTALL_COMPLETED,
                    notice_version=state.consent_notice_version or CONSENT_NOTICE_VERSION,
                )
            elif state.last_reported_version != current:
                event = build_event(
                    EventType.UPDATE_COMPLETED,
                    notice_version=state.consent_notice_version or CONSENT_NOTICE_VERSION,
                    previous_version=state.last_reported_version,
                )
            else:
                self._save(state)
                return
            await self._send_or_queue(state, event)
            self._save(state)

    async def start(self) -> None:
        """Apply explicit installer policy and start the low-frequency local checker."""
        mode = os.getenv("SHOGUN_TELEMETRY", "").strip().casefold()
        notice = os.getenv("SHOGUN_TELEMETRY_NOTICE_VERSION", "").strip()
        if mode == "off":
            state = self._load()
            if state.enabled:
                state.enabled = False
                state.telemetry_token = None
                state.next_scheduled_at = None
                state.queue = []
                state.last_result = "Disabled by administrator policy"
                self._save(state)
        elif mode == "on" and notice == CONSENT_NOTICE_VERSION and not self._load().enabled:
            await self.enable(
                notice,
                actor="installer",
                register_immediately=False,
            )
        elif mode == "on":
            state = self._load()
            state.enabled = False
            state.last_result = "Disabled: valid telemetry notice acceptance is required"
            self._save(state)
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._scheduler())
        state = self._load()
        if state.enabled and (self._delivery_task is None or self._delivery_task.done()):
            self._delivery_task = asyncio.create_task(self._initial_delivery())

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._delivery_task:
            self._delivery_task.cancel()
            try:
                await self._delivery_task
            except asyncio.CancelledError:
                pass
            self._delivery_task = None


telemetry_service = TelemetryService()
