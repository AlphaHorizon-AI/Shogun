from datetime import datetime, timezone
from types import SimpleNamespace


def test_telemetry_is_enabled_by_default_and_hides_private_salt(monkeypatch, tmp_path):
    import shogun.services.college_telemetry as telemetry

    monkeypatch.setattr(telemetry, "CONFIG_PATH", tmp_path / "telemetry.json")
    assert telemetry.public_config()["enabled"] is True
    saved = telemetry.save_config(enabled=False)
    assert saved["enabled"] is False
    assert "installation_salt" not in saved
    assert "prompts" in saved["never_shared"]


def test_existing_opt_out_is_preserved(monkeypatch, tmp_path):
    import shogun.services.college_telemetry as telemetry

    config_path = tmp_path / "telemetry.json"
    config_path.write_text('{"enabled": false, "installation_salt": "existing"}', encoding="utf-8")
    monkeypatch.setattr(telemetry, "CONFIG_PATH", config_path)

    assert telemetry.public_config()["enabled"] is False
    assert telemetry.load_config()["installation_salt"] == "existing"


def test_model_usage_payload_is_coarse_and_contains_no_content(monkeypatch, tmp_path):
    import shogun.services.college_telemetry as telemetry

    monkeypatch.setattr(telemetry, "CONFIG_PATH", tmp_path / "telemetry.json")
    monkeypatch.setattr(telemetry, "_country_code", lambda: "DK")
    telemetry.save_config(enabled=True)
    body = SimpleNamespace(
        model_id="gpt-5",
        provider="openai",
        input_tokens=3500,
        output_tokens=900,
        latency_ms=2400,
        estimated_cost=0.04,
        success=True,
    )
    payload = telemetry.build_model_usage_event(
        body,
        SimpleNamespace(task_type="coding"),
        datetime(2026, 7, 21, 12, 34, tzinfo=timezone.utc),
    )
    assert payload["country"] == "DK"
    assert payload["inputTokens"] == "1k-4k"
    assert payload["latency"] == "1-3s"
    assert payload["cost"] == "$0.01-0.10"
    assert payload["taskType"] == "coding"
    assert payload["occurredAt"] == "2026-07-21T12:00:00+00:00"
    assert not ({"prompt", "output", "error", "agent", "ip"} & payload.keys())
