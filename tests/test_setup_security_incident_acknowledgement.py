from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from shogun.api import setup as setup_api
from shogun.api.setup import (
    LICENSE_TERMS_ACCEPTANCE_STATEMENT,
    SECURITY_INCIDENT_ACKNOWLEDGEMENT_STATEMENT,
    SetupCompletePayload,
)
from shogun.telemetry import payload as telemetry_payload
from shogun.telemetry.models import EventType


def test_setup_completion_requires_explicit_security_acknowledgement() -> None:
    with pytest.raises(ValidationError, match="security_incident_acknowledged"):
        SetupCompletePayload()

    with pytest.raises(ValidationError, match="Input should be True"):
        SetupCompletePayload(
            security_incident_acknowledged=False,
            license_terms_accepted=True,
        )

    payload = SetupCompletePayload(
        security_incident_acknowledged=True,
        license_terms_accepted=True,
    )
    assert payload.security_incident_acknowledged is True


def test_setup_completion_requires_explicit_license_acceptance() -> None:
    with pytest.raises(ValidationError, match="license_terms_accepted"):
        SetupCompletePayload(security_incident_acknowledged=True)

    with pytest.raises(ValidationError, match="Input should be True"):
        SetupCompletePayload(
            security_incident_acknowledged=True,
            license_terms_accepted=False,
        )


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
        "acknowledged_by_role": "installer",
        "installed_version": "9.8.7",
        "installed_build": 654,
        "installed_release_identifier": "9.8.7+build.654",
        "installed_release_date": "2026-08-21T12:34:56Z",
    }
    assert datetime.fromisoformat(record["acknowledged_at"]).tzinfo is not None


def test_license_acceptance_is_tied_to_bundled_release(
    tmp_path: Path,
    monkeypatch,
) -> None:
    license_bytes = b"exact bundled licence\n"
    (tmp_path / "LICENSE.md").write_bytes(license_bytes)
    monkeypatch.setattr(setup_api, "PROJECT_ROOT", tmp_path)
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

    record = setup_api._license_terms_acceptance()

    assert record == {
        "record_version": 1,
        "statement": LICENSE_TERMS_ACCEPTANCE_STATEMENT,
        "accepted_at": record["accepted_at"],
        "accepted_by_role": "installer",
        "license_file": "LICENSE.md",
        "license_sha256": hashlib.sha256(license_bytes).hexdigest(),
        "installed_version": "9.8.7",
        "installed_build": 654,
        "installed_release_identifier": "9.8.7+build.654",
        "installed_release_date": "2026-08-21T12:34:56Z",
    }
    assert datetime.fromisoformat(record["accepted_at"]).tzinfo is not None


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
        "license_terms_acceptance",
        "license_terms_accepted",
        "license_sha256",
        "accepted_at",
        "accepted_by_role",
        "license_file",
    ):
        with pytest.raises(ValueError, match="Forbidden telemetry field"):
            telemetry_payload.enforce_payload({**event, key: "must-stay-local"})


def test_installer_and_guide_include_security_routes() -> None:
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
    assert "import licenseText from '../../../LICENSE.md?raw'" in wizard
    assert "license_terms_accepted: licenseTermsAccepted" in wizard
    assert "disabled={completing || !licenseTermsAccepted}" in wizard
    assert LICENSE_TERMS_ACCEPTANCE_STATEMENT in wizard
    assert "https://github.com/AlphaHorizon-AI/Shogun/issues/new" in wizard
    assert "https://github.com/AlphaHorizon-AI/Shogun/security/advisories/new" in wizard
    assert "mailto:contact@alphahorizon.io?subject=Shogun%20Security%20Report" in wizard
    assert 'rel="noopener noreferrer"' in wizard
    assert "Incident Reporting" not in sidebar
    assert "Guide → Reference → Incident Reporting" in english["setup"]["security_post_install"]
    assert "requestedGuideTab(location.search)" in guide
    assert "requestedGuideSection(" in guide
    assert "decodeURIComponent(hash.slice(1))" in navigation
