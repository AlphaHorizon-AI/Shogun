from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from shogun.api import setup as setup_api
from shogun.api.setup import (
    SECURITY_INCIDENT_ACKNOWLEDGEMENT_STATEMENT,
    SetupCompletePayload,
)
from shogun.telemetry import payload as telemetry_payload
from shogun.telemetry.models import EventType


def test_setup_completion_requires_explicit_security_acknowledgement() -> None:
    with pytest.raises(ValidationError, match="security_incident_acknowledged"):
        SetupCompletePayload()

    with pytest.raises(ValidationError, match="Input should be True"):
        SetupCompletePayload(security_incident_acknowledged=False)

    payload = SetupCompletePayload(security_incident_acknowledged=True)
    assert payload.security_incident_acknowledged is True


def test_acknowledgement_uses_server_release_metadata(monkeypatch) -> None:
    monkeypatch.setattr(
        setup_api,
        "_installation_release_metadata",
        lambda: {
            "version": "9.8.7",
            "build": 654,
            "release_id": "9.8.7+build.654",
            "release_date": "2026-08-21T12:34:56Z",
        },
    )

    record = setup_api._security_incident_acknowledgement("team")

    assert record == {
        "record_version": 1,
        "statement": SECURITY_INCIDENT_ACKNOWLEDGEMENT_STATEMENT,
        "acknowledged_at": record["acknowledged_at"],
        "acknowledged_by_role": "primary_admin",
        "installed_version": "9.8.7",
        "installed_build": 654,
        "installed_release_identifier": "9.8.7+build.654",
        "installed_release_date": "2026-08-21T12:34:56Z",
    }
    assert datetime.fromisoformat(record["acknowledged_at"]).tzinfo is not None


def test_local_acknowledgement_is_never_serialized_as_telemetry(
    tmp_path: Path,
    monkeypatch,
) -> None:
    acknowledgement = {
        "record_version": 1,
        "statement": SECURITY_INCIDENT_ACKNOWLEDGEMENT_STATEMENT,
        "acknowledged_at": "2026-08-21T12:34:56+00:00",
        "acknowledged_by_role": "primary_admin",
        "installed_version": "9.8.7",
        "installed_build": 654,
        "installed_release_identifier": "9.8.7+build.654",
        "installed_release_date": "2026-08-21T12:34:56Z",
    }
    (tmp_path / "setup.json").write_text(
        json.dumps(
            {
                "installation_mode": "team",
                "security_incident_acknowledgement": acknowledgement,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(telemetry_payload.settings, "config_path", tmp_path)

    event = telemetry_payload.build_event(EventType.INSTALL_COMPLETED).model_dump(
        mode="json", exclude_none=True
    )
    serialized = json.dumps(event, sort_keys=True)

    assert set(acknowledgement).isdisjoint(event)
    assert SECURITY_INCIDENT_ACKNOWLEDGEMENT_STATEMENT not in serialized
    assert "security_incident_acknowledgement" not in serialized
    for key in (
        "security_incident_acknowledgement",
        "security_incident_acknowledged",
        "acknowledged_at",
        "acknowledged_by_role",
        "installed_release_identifier",
    ):
        with pytest.raises(ValueError, match="Forbidden telemetry field"):
            telemetry_payload.enforce_payload({**event, key: "must-stay-local"})


def test_installer_and_persistent_navigation_include_security_routes() -> None:
    root = Path(__file__).resolve().parents[1]
    english = json.loads((root / "frontend/src/i18n/en.json").read_text(encoding="utf-8"))
    wizard = (root / "frontend/src/pages/SetupWizard.tsx").read_text(encoding="utf-8")
    sidebar = (root / "frontend/src/components/layout/Sidebar.tsx").read_text(encoding="utf-8")
    guide = (root / "frontend/src/pages/Guide.tsx").read_text(encoding="utf-8")
    navigation = (root / "frontend/src/lib/guideNavigation.ts").read_text(encoding="utf-8")

    assert "const TOTAL_STEPS = 10" in wizard
    assert english["setup"]["security_acknowledgement"] == (
        SECURITY_INCIDENT_ACKNOWLEDGEMENT_STATEMENT
    )
    assert "security_incident_acknowledged: securityIncidentAcknowledged" in wizard
    assert "https://github.com/AlphaHorizon-AI/Shogun/issues/new" in wizard
    assert "https://github.com/AlphaHorizon-AI/Shogun/security/advisories/new" in wizard
    assert "mailto:contact@alphahorizon.io?subject=Shogun%20Security%20Report" in wizard
    assert 'rel="noopener noreferrer"' in wizard
    assert "/guide?tab=reference#ref-incident-reporting" in sidebar
    assert "requestedGuideTab(location.search)" in guide
    assert "requestedGuideSection(" in guide
    assert "decodeURIComponent(hash.slice(1))" in navigation
