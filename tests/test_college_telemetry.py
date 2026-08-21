import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest


def test_telemetry_is_disabled_by_default_and_hides_private_salt(monkeypatch, tmp_path):
    import shogun.services.college_telemetry as telemetry

    monkeypatch.setattr(telemetry, "CONFIG_PATH", tmp_path / "telemetry.json")
    assert telemetry.public_config()["enabled"] is False
    assert telemetry.load_config()["installation_salt"] == ""
    saved = telemetry.save_config(enabled=False)
    assert saved["enabled"] is False
    assert "installation_salt" not in saved
    assert "prompt or output content as dedicated fields" in saved["never_shared"]
    assert saved["endpoint"] == telemetry.INGEST_URL
    assert saved["request_method"] == "POST"
    assert saved["request_envelope"] == "events[]"
    assert saved["shared_fields"] == list(telemetry.MODEL_USAGE_EVENT_FIELDS)
    details = {
        item["field"]: item["description"]
        for item in saved["shared_field_details"]
    }
    assert set(details) == set(telemetry.MODEL_USAGE_EVENT_FIELDS)
    assert "sent verbatim" in details["model"]
    assert "sent verbatim" in details["provider"]
    assert "sent verbatim" in details["taskType"]
    assert "country code derived from the OS or locale" in details["country"]
    assert "rotated each ISO week" in details["installationHash"]
    assert "rounded down to the hour" in details["occurredAt"]
    assert "bucketed" in details["inputTokens"]
    assert "Do not opt in" in saved["identifier_warning"]
    assert "customer" in saved["identifier_warning"]
    assert "credential" in saved["identifier_warning"]
    assert "ecosystem benchmarks" in saved["purpose"]
    assert "acknowledgement" in " ".join(saved["never_shared"])


def test_existing_opt_out_is_preserved(monkeypatch, tmp_path):
    import shogun.services.college_telemetry as telemetry

    config_path = tmp_path / "telemetry.json"
    config_path.write_text('{"enabled": false, "installation_salt": "existing"}', encoding="utf-8")
    monkeypatch.setattr(telemetry, "CONFIG_PATH", config_path)

    assert telemetry.public_config()["enabled"] is False
    assert telemetry.load_config()["installation_salt"] == ""


def test_legacy_implicit_opt_in_is_failed_closed(monkeypatch, tmp_path):
    import shogun.services.college_telemetry as telemetry

    config_path = tmp_path / "telemetry.json"
    config_path.write_text(
        '{"enabled": true, "schema_version": 1, "installation_salt": "legacy"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(telemetry, "CONFIG_PATH", config_path)

    config = telemetry.load_config()
    assert config["enabled"] is False
    assert config["installation_salt"] == ""
    body = SimpleNamespace(
        model_id="legacy-model",
        provider="ollama",
        input_tokens=1,
        output_tokens=1,
        latency_ms=1,
        estimated_cost=0,
        success=True,
    )
    assert telemetry.queue_model_usage(body) is False
    assert telemetry._tasks == set()


def test_enabling_requires_explicit_current_notice(monkeypatch, tmp_path):
    import shogun.services.college_telemetry as telemetry

    monkeypatch.setattr(telemetry, "CONFIG_PATH", tmp_path / "telemetry.json")
    with pytest.raises(ValueError, match="explicit acceptance"):
        telemetry.save_config(enabled=True)
    with pytest.raises(ValueError, match="explicit acceptance"):
        telemetry.save_config(enabled=True, notice_version="old", confirmed=True)

    saved = telemetry.save_config(
        enabled=True,
        notice_version=telemetry.CONSENT_NOTICE_VERSION,
        confirmed=True,
    )
    assert saved["enabled"] is True
    assert saved["consented_at"]


@pytest.mark.asyncio
async def test_local_admin_api_requires_affirmative_college_consent(monkeypatch, tmp_path):
    from fastapi import HTTPException

    import shogun.services.college_telemetry as telemetry
    from shogun.api.system import CollegeTelemetryUpdate, update_college_telemetry_settings

    monkeypatch.setattr(telemetry, "CONFIG_PATH", tmp_path / "telemetry.json")

    with pytest.raises(HTTPException) as error:
        await update_college_telemetry_settings(CollegeTelemetryUpdate(enabled=True))
    assert error.value.status_code == 400

    response = await update_college_telemetry_settings(
        CollegeTelemetryUpdate(
            enabled=True,
            notice_version=telemetry.CONSENT_NOTICE_VERSION,
            confirmed=True,
        )
    )
    assert response.data["enabled"] is True


def test_model_usage_payload_matches_disclosure_and_contains_no_content(monkeypatch, tmp_path):
    import shogun.services.college_telemetry as telemetry

    monkeypatch.setattr(telemetry, "CONFIG_PATH", tmp_path / "telemetry.json")
    monkeypatch.setattr(telemetry, "_country_code", lambda: "DK")
    telemetry.save_config(
        enabled=True,
        notice_version=telemetry.CONSENT_NOTICE_VERSION,
        confirmed=True,
    )
    body = SimpleNamespace(
        model_id="configured-project-model",
        provider="configured-provider",
        input_tokens=3500,
        output_tokens=900,
        latency_ms=2400,
        estimated_cost=0.04,
        success=True,
        security_incident_acknowledged=True,
        security_incident_acknowledgement={"statement": "must stay local"},
    )
    payload = telemetry.build_model_usage_event(
        body,
        SimpleNamespace(task_type="coding"),
        datetime(2026, 7, 21, 12, 34, tzinfo=timezone.utc),
    )
    assert payload["country"] == "DK"
    assert payload["model"] == "configured-project-model"
    assert payload["provider"] == "configured-provider"
    assert payload["inputTokens"] == "1k-4k"
    assert payload["latency"] == "1-3s"
    assert payload["cost"] == "$0.01-0.10"
    assert payload["taskType"] == "coding"
    assert payload["occurredAt"] == "2026-07-21T12:00:00+00:00"
    assert set(payload) == set(telemetry.MODEL_USAGE_EVENT_FIELDS)
    assert not ({"prompt", "output", "error", "agent", "ip"} & payload.keys())
    assert "acknowledgement" not in " ".join(payload).lower()


def test_privacy_ui_renders_identifier_warning_and_exact_field_details():
    from pathlib import Path

    source = Path("frontend/src/pages/PrivacyTelemetry.tsx").read_text(encoding="utf-8")
    assert "Identifiers and bucketed metrics sent" in source
    assert "collegeTelemetry?.shared_field_details" in source
    assert "collegeTelemetry.identifier_warning" in source
    assert "Coarse signals only" not in source


@pytest.mark.asyncio
async def test_no_queue_or_delivery_before_opt_in_and_opt_in_enables_it(monkeypatch, tmp_path):
    import shogun.services.college_telemetry as telemetry

    monkeypatch.setattr(telemetry, "CONFIG_PATH", tmp_path / "telemetry.json")
    deliveries = []

    async def fake_deliver(payload):
        deliveries.append(payload)

    monkeypatch.setattr(telemetry, "_deliver", fake_deliver)
    body = SimpleNamespace(
        model_id="local-model",
        provider="ollama",
        input_tokens=10,
        output_tokens=10,
        latency_ms=10,
        estimated_cost=0,
        success=True,
    )

    assert telemetry.queue_model_usage(body) is False
    await asyncio.sleep(0)
    assert deliveries == []
    assert telemetry._tasks == set()

    telemetry.save_config(
        enabled=True,
        notice_version=telemetry.CONSENT_NOTICE_VERSION,
        confirmed=True,
    )
    assert telemetry.queue_model_usage(body) is True
    await asyncio.gather(*tuple(telemetry._tasks))
    assert len(deliveries) == 1


@pytest.mark.asyncio
async def test_delivery_rejects_fields_outside_the_disclosed_schema(monkeypatch, tmp_path):
    import shogun.services.college_telemetry as telemetry

    monkeypatch.setattr(telemetry, "CONFIG_PATH", tmp_path / "telemetry.json")
    telemetry.save_config(
        enabled=True,
        notice_version=telemetry.CONSENT_NOTICE_VERSION,
        confirmed=True,
    )

    class NetworkMustNotStart:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("an undisclosed payload must never reach the network")

    monkeypatch.setattr(telemetry.httpx, "AsyncClient", NetworkMustNotStart)
    body = SimpleNamespace(
        model_id="local-model",
        provider="ollama",
        input_tokens=10,
        output_tokens=10,
        latency_ms=10,
        estimated_cost=0,
        success=True,
    )
    payload = telemetry.build_model_usage_event(body)
    payload["security_incident_acknowledgement"] = "must remain local"

    await telemetry._deliver(payload)

    assert telemetry._last_status["state"] == "rejected"


def test_college_opt_in_does_not_enable_alpha_horizon_installation_telemetry(
    monkeypatch,
    tmp_path,
):
    import shogun.services.college_telemetry as college
    from shogun.telemetry.service import TelemetryService

    monkeypatch.setattr(college, "CONFIG_PATH", tmp_path / "college.json")
    installation = TelemetryService(state_path=tmp_path / "installation.json")

    college.save_config(
        enabled=True,
        notice_version=college.CONSENT_NOTICE_VERSION,
        confirmed=True,
    )

    assert college.public_config()["enabled"] is True
    assert installation.status()["enabled"] is False
    assert not (tmp_path / "installation.json").exists()
