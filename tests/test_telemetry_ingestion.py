from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from shogun.telemetry.models import EventType
from shogun.telemetry.payload import build_event, build_registration
from telemetry_service.schemas import EventBatch
from telemetry_service.security import hash_token, installation_key, nonce_key


def test_server_schema_rejects_unknown_and_forbidden_fields():
    event = build_event(EventType.INSTALL_COMPLETED).model_dump(mode="json")
    with pytest.raises(ValidationError):
        EventBatch.model_validate({"events": [{**event, "message": "private"}]})
    with pytest.raises(ValidationError):
        EventBatch.model_validate({"events": [event], "metadata": {}})


def test_server_batch_limit_is_ten():
    event = build_event(EventType.ACTIVE_HEARTBEAT).model_dump(mode="json")
    EventBatch.model_validate({"events": [event] * 10})
    with pytest.raises(ValidationError):
        EventBatch.model_validate({"events": [event] * 11})


def test_hmac_identity_and_token_hash_do_not_store_raw_values(monkeypatch):
    from telemetry_service import security

    monkeypatch.setattr(security.settings, "hmac_secret", "x" * 64)
    identifier = str(uuid4())
    nonce = str(uuid4())
    token = "opaque-" + ("z" * 64)
    assert identifier not in installation_key(identifier)
    assert nonce not in nonce_key(nonce)
    assert token not in hash_token(token)
    assert len(installation_key(identifier)) == 64


def test_registration_has_no_identity_or_machine_fields():
    registration = build_registration(uuid4(), uuid4(), "1.0").model_dump(mode="json")
    assert set(registration) == {
        "schema_version", "installation_id", "instance_nonce",
        "consent_notice_version", "shogun_version", "build_id",
        "release_channel", "distribution_channel", "platform_family",
        "architecture", "install_type", "operation_mode",
    }
    assert not {
        "hostname", "machine_id", "ip_address", "email", "organization_name", "metadata"
    } & set(registration)


def test_register_submit_duplicate_and_delete_end_to_end(monkeypatch):
    from telemetry_service import security
    from telemetry_service.app import delete_self, register, submit_events
    from telemetry_service.db import Base
    from telemetry_service.db_models import Event, Installation

    monkeypatch.setattr(security.settings, "hmac_secret", "h" * 64)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    installation_id = uuid4()
    nonce = uuid4()
    registration = build_registration(installation_id, nonce, "1.0")

    with Session(engine) as db:
        result = register(registration, db)
        assert len(result.telemetry_token) >= 32
        stored = db.scalar(select(Installation))
        assert stored is not None
        assert stored.installation_key != str(installation_id)
        assert stored.token_hash != result.telemetry_token

        event = build_event(EventType.INSTALL_COMPLETED)
        batch = EventBatch(events=[event])
        accepted = submit_events(
            batch,
            authorization=f"Bearer {result.telemetry_token}",
            db=db,
        )
        assert accepted.status == "accepted"
        assert accepted.accepted == 1
        duplicate = submit_events(
            batch,
            authorization=f"Bearer {result.telemetry_token}",
            db=db,
        )
        assert duplicate.status == "duplicate"
        assert db.scalar(select(func.count(Event.event_id))) == 1

        revoked = submit_events(
            EventBatch(events=[build_event(EventType.CONSENT_REVOKED)]),
            authorization=f"Bearer {result.telemetry_token}",
            db=db,
        )
        assert revoked.status == "accepted"
        assert db.scalar(select(func.count(Event.event_id))) == 0

        deleted = delete_self(
            authorization=f"Bearer {result.telemetry_token}",
            db=db,
        )
        assert deleted == {"status": "accepted"}
        assert db.scalar(select(func.count(Installation.installation_key))) == 0
        assert db.scalar(select(func.count(Event.event_id))) == 0
