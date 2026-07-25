"""Alpha Horizon installation telemetry ingestion API."""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.orm import Session

from telemetry_service.config import settings
from telemetry_service.db import Base, engine, get_db
from telemetry_service.db_models import AdminAudit, ConsentHistory, Event, Installation
from telemetry_service.schemas import (
    EventBatch,
    EventResult,
    RegistrationRequest,
    RegistrationResult,
)
from telemetry_service.security import (
    hash_token,
    installation_key,
    nonce_key,
    require_identity_proxy,
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.validate_production()
    Base.metadata.create_all(engine)
    yield


app = FastAPI(
    title="Alpha Horizon Shogun Installation Telemetry",
    version="1.0",
    lifespan=lifespan,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None,
)


@app.middleware("http")
async def enforce_request_contract(request: Request, call_next):
    if request.url.path in {"/v1/installations/register", "/v1/events"}:
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "JSON requests only"}, status_code=415)
        body = await request.body()
        limit = 32 * 1024 if request.url.path == "/v1/events" else 4 * 1024
        if len(body) > limit:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store"
    return response


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Installation token required")
    token = authorization[7:]
    if len(token) < 32 or len(token) > 512:
        raise HTTPException(401, "Invalid installation token")
    return token


def _installation_for_token(
    db: Session,
    authorization: str | None,
    *,
    allow_revoked: bool = False,
) -> Installation:
    record = db.scalar(
        select(Installation).where(Installation.token_hash == hash_token(_bearer(authorization)))
    )
    if not record:
        raise HTTPException(401, "Invalid installation token")
    if record.status != "active" and not allow_revoked:
        raise HTTPException(403, "Installation telemetry is revoked")
    return record


@app.post("/v1/installations/register", response_model=RegistrationResult)
def register(payload: RegistrationRequest, db: Session = Depends(get_db)):
    key = installation_key(str(payload.installation_id))
    nonce = nonce_key(str(payload.instance_nonce))
    record = db.get(Installation, key)
    if record and record.instance_nonce_key != nonce:
        raise HTTPException(409, "clone_conflict")
    token = secrets.token_urlsafe(48)
    values = {
        "instance_nonce_key": nonce,
        "token_hash": hash_token(token),
        "status": "active",
        "last_version": payload.shogun_version,
        "build_id": payload.build_id,
        "release_channel": payload.release_channel.value,
        "distribution_channel": payload.distribution_channel.value,
        "platform_family": payload.platform_family.value,
        "architecture": payload.architecture,
        "install_type": payload.install_type.value,
        "operation_mode": payload.operation_mode.value,
        "consent_notice_version": payload.consent_notice_version,
        "updated_at": datetime.now(UTC),
    }
    if record:
        for name, value in values.items():
            setattr(record, name, value)
    else:
        record = Installation(installation_key=key, **values)
        db.add(record)
        db.add(ConsentHistory(
            installation_key=key,
            action="consent_registered",
            notice_version=payload.consent_notice_version,
        ))
    db.commit()
    return RegistrationResult(telemetry_token=token)


@app.post("/v1/events", response_model=EventResult)
def submit_events(
    payload: EventBatch,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    installation = _installation_for_token(db, authorization)
    now = datetime.now(UTC)
    accepted = 0
    duplicate = False
    daily_count = db.scalar(
        select(func.count(Event.event_id)).where(
            Event.installation_key == installation.installation_key,
            Event.received_at >= now - timedelta(days=1),
        )
    ) or 0
    if daily_count + len(payload.events) > 20:
        return EventResult(status="retry_after")
    for event in payload.events:
        occurred_at = event.occurred_at
        if occurred_at < now - timedelta(days=30) or occurred_at > now + timedelta(hours=24):
            return EventResult(status="invalid")
        if db.get(Event, str(event.event_id)):
            duplicate = True
            continue
        if event.event_type.value == "consent_revoked":
            # Withdrawal immediately removes linkable raw history. The consent
            # action remains only in the pseudonymous accountability table until
            # the subsequent self-deletion request removes the installation.
            db.execute(delete(Event).where(
                Event.installation_key == installation.installation_key
            ))
            installation.status = "revoked"
            installation.revoked_at = now
            installation.updated_at = now
            db.add(ConsentHistory(
                installation_key=installation.installation_key,
                action="consent_revoked",
                notice_version=installation.consent_notice_version,
            ))
            accepted += 1
            continue
        counted = True
        if event.event_type.value == "active_heartbeat":
            recent = db.scalar(
                select(Event.event_id).where(
                    Event.installation_key == installation.installation_key,
                    Event.event_type == "active_heartbeat",
                    Event.counted.is_(True),
                    Event.received_at >= now - timedelta(days=5),
                ).limit(1)
            )
            counted = recent is None
        db.add(Event(
            event_id=str(event.event_id),
            installation_key=installation.installation_key,
            event_type=event.event_type.value,
            occurred_at=occurred_at,
            shogun_version=event.shogun_version,
            build_id=event.build_id,
            release_channel=event.release_channel.value,
            distribution_channel=event.distribution_channel.value,
            platform_family=event.platform_family.value,
            architecture=event.architecture,
            install_type=event.install_type.value,
            operation_mode=event.operation_mode.value,
            schema_version=event.schema_version,
            counted=counted and event.event_type.value != "telemetry_test",
        ))
        accepted += 1
        installation.last_seen_at = now
        installation.last_version = event.shogun_version
        installation.updated_at = now
    db.commit()
    return EventResult(status="duplicate" if duplicate and not accepted else "accepted", accepted=accepted)


@app.get("/v1/installations/self/export")
def export_self(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    installation = _installation_for_token(db, authorization)
    events = list(db.scalars(select(Event).where(
        Event.installation_key == installation.installation_key
    )))
    return {
        "installation": {
            key: getattr(installation, key)
            for key in (
                "status", "registered_at", "last_seen_at", "last_version", "build_id",
                "release_channel", "distribution_channel", "platform_family",
                "architecture", "install_type", "operation_mode", "consent_notice_version",
            )
        },
        "events": [
            {
                key: getattr(event, key)
                for key in (
                    "event_id", "event_type", "occurred_at", "received_at",
                    "shogun_version", "build_id", "release_channel",
                    "distribution_channel", "platform_family", "architecture",
                    "install_type", "operation_mode", "schema_version",
                )
            }
            for event in events
        ],
    }


@app.delete("/v1/installations/self")
def delete_self(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    installation = _installation_for_token(db, authorization, allow_revoked=True)
    key = installation.installation_key
    notice = installation.consent_notice_version
    db.execute(delete(Event).where(Event.installation_key == key))
    db.execute(delete(ConsentHistory).where(ConsentHistory.installation_key == key))
    db.delete(installation)
    db.flush()
    db.add(ConsentHistory(
        installation_key=None,
        action="deletion_completed",
        notice_version=notice,
    ))
    db.commit()
    return {"status": "accepted"}


@app.get("/v1/schema")
def schema():
    return {
        "schema_version": 1,
        "consent_notice_version": "1.0",
        "event_types": [
            "install_completed", "update_completed", "active_heartbeat",
            "consent_revoked", "telemetry_test",
        ],
        "heartbeat_interval_seconds": 604800,
    }


def _audit(db: Session, actor: str, action: str) -> None:
    db.add(AdminAudit(actor=actor, action=action))
    db.commit()


@app.get("/internal/v1/dashboard/summary")
def dashboard_summary(
    actor: str = Depends(require_identity_proxy),
    db: Session = Depends(get_db),
):
    now = datetime.now(UTC)
    total = db.scalar(select(func.count(Installation.installation_key))) or 0
    active7 = db.scalar(select(func.count(distinct(Event.installation_key))).where(
        Event.event_type == "active_heartbeat",
        Event.counted.is_(True),
        Event.occurred_at >= now - timedelta(days=7),
    )) or 0
    active30 = db.scalar(select(func.count(distinct(Event.installation_key))).where(
        Event.event_type == "active_heartbeat",
        Event.counted.is_(True),
        Event.occurred_at >= now - timedelta(days=30),
    )) or 0
    revoked = db.scalar(select(func.count(Installation.installation_key)).where(
        Installation.status == "revoked"
    )) or 0
    versions = dict(db.execute(select(
        Installation.last_version, func.count(Installation.installation_key)
    ).group_by(Installation.last_version)).all())
    platforms = dict(db.execute(select(
        Installation.platform_family, func.count(Installation.installation_key)
    ).group_by(Installation.platform_family)).all())
    _audit(db, actor, "dashboard.summary.view")
    return {
        "total_registered_installations": total,
        "active_installations_7_days": active7,
        "active_installations_30_days": active30,
        "revoked_installations": revoked,
        "version_distribution": versions,
        "platform_distribution": platforms,
        "warning": (
            "Telemetry includes only installations that voluntarily opted in. "
            "Counts are adoption indicators, not a complete customer census."
        ),
    }


@app.get("/internal/v1/dashboard/adoption")
def dashboard_adoption(
    days: int = 30,
    group_by: Literal[
        "shogun_version", "release_channel", "distribution_channel",
        "platform_family", "architecture", "install_type", "operation_mode",
    ] = "shogun_version",
    version: str | None = None,
    release_channel: Literal["stable", "beta", "development"] | None = None,
    platform_family: Literal["windows", "linux", "macos", "other"] | None = None,
    install_type: Literal["native", "docker", "headless_server", "development"] | None = None,
    operation_mode: Literal["single_user", "team"] | None = None,
    distribution_channel: Literal[
        "official_installer", "official_docker", "source_checkout",
        "authorized_community_build", "unknown",
    ] | None = None,
    actor: str = Depends(require_identity_proxy),
    db: Session = Depends(get_db),
):
    """Aggregate adoption chart data; never returns installation-level rows."""
    if not 1 <= days <= 730:
        raise HTTPException(400, "days must be between 1 and 730")
    since = datetime.now(UTC) - timedelta(days=days)
    conditions = [Event.occurred_at >= since, Event.counted.is_(True)]
    filters = {
        Event.shogun_version: version,
        Event.release_channel: release_channel,
        Event.platform_family: platform_family,
        Event.install_type: install_type,
        Event.operation_mode: operation_mode,
        Event.distribution_channel: distribution_channel,
    }
    for column, value in filters.items():
        if value is not None:
            conditions.append(column == value)
    grouping_column = getattr(Event, group_by)
    distribution = dict(db.execute(
        select(grouping_column, func.count(distinct(Event.installation_key)))
        .where(*conditions)
        .group_by(grouping_column)
    ).all())
    by_day = [
        {"date": str(day), "event_type": event_type, "installations": count}
        for day, event_type, count in db.execute(
            select(
                func.date(Event.occurred_at),
                Event.event_type,
                func.count(distinct(Event.installation_key)),
            )
            .where(*conditions)
            .group_by(func.date(Event.occurred_at), Event.event_type)
            .order_by(func.date(Event.occurred_at))
        ).all()
    ]
    _audit(db, actor, "dashboard.adoption.view")
    return {
        "period_days": days,
        "group_by": group_by,
        "distribution": distribution,
        "daily_series": by_day,
        "warning": (
            "Opt-in installation counts only; one installation may serve multiple "
            "people and one operator may run multiple installations."
        ),
    }


@app.get("/internal/dashboard", response_class=HTMLResponse)
def dashboard(
    actor: str = Depends(require_identity_proxy),
    db: Session = Depends(get_db),
):
    _audit(db, actor, "dashboard.page.view")
    return """<!doctype html><html><head><meta charset="utf-8"><title>Shogun Adoption Console</title>
<style>body{font:16px system-ui;background:#090b10;color:#e7e7e7;max-width:1100px;margin:3rem auto}
.card{border:1px solid #313746;border-radius:12px;padding:1.5rem;background:#121620}
code{color:#efc66b}</style></head><body><h1>Shogun Adoption Console</h1>
<div class="card"><p>This console exposes aggregate, opt-in installation metrics only.</p>
<p>Use <code>/internal/v1/dashboard/summary</code> through the authenticated identity proxy.
No individual installation timeline is available.</p></div></body></html>"""


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(select(1))
    return {"status": "ready"}
