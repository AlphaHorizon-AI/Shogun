"""Static guards for the required security-hardening CI boundary."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "security-hardening.yml"
CODEQL_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "codeql.yml"
RELEASE_EVIDENCE_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release-evidence.yml"

REQUIRED_REGRESSION_TESTS = {
    "tests/test_college_telemetry.py",
    "tests/test_cascade_retrieval.py",
    "tests/test_chat_sync.py",
    "tests/test_gensui_identity_boundaries.py",
    "tests/test_gensui_installer_hardening.py",
    "tests/test_guide_incident_reporting.py",
    "tests/test_install_telemetry.py",
    "tests/test_installer_release_provenance.py",
    "tests/test_red_team_hardening.py",
    "tests/test_release_evidence.py",
    "tests/test_release_metadata.py",
    "tests/test_ronin_desktop_control.py",
    "tests/test_ronin_runtime_security_gates.py",
    "tests/test_security_governance_language.py",
    "tests/test_security_parsing_regressions.py",
    "tests/test_security_posture.py",
    "tests/test_security_workflow_gate.py",
    "tests/test_server_mode.py",
    "tests/test_server_setup_url.py",
    "tests/test_setup_routing.py",
    "tests/test_setup_security_incident_acknowledgement.py",
    "tests/test_team_mode_setup.py",
    "tests/test_telemetry_ingestion.py",
    "tests/test_update_checker.py",
    "tests/test_update_provenance.py",
    "tests/test_updates.py",
}

REQUIRED_RUFF_BOUNDARIES = {
    "scripts/generate_release_evidence.py",
    "scripts/write_release_metadata_evidence.py",
    "shogun/api/ronin.py",
    "shogun/api/security.py",
    "shogun/api/setup.py",
    "shogun/api/updates.py",
    "shogun/ronin/core/approval_gate.py",
    "shogun/ronin/core/action_router.py",
    "shogun/ronin/core/audit_logger.py",
    "shogun/ronin/core/capabilities_registry.py",
    "shogun/ronin/core/posture_guard.py",
    "shogun/ronin/core/ronin_controller.py",
    "shogun/ronin/policies/ronin_policy_schema.py",
    "shogun/schemas/ronin.py",
    "shogun/services/college_telemetry.py",
    "shogun/services/cascade_retrieval.py",
    "shogun/services/chat_sync_service.py",
    "shogun/services/event_logger.py",
    "shogun/services/release_metadata.py",
    "shogun/services/update_checker.py",
    "shogun/services/telegram_poller.py",
    "shogun/setup_link.py",
    "shogun/telemetry/payload.py",
    "gensui/api/fleet_audit.py",
    "gensui/api/identity.py",
    "gensui/api/deps.py",
    "gensui/services/identity_service.py",
} | REQUIRED_REGRESSION_TESTS

PINNED_ACTIONS = {
    "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803": "v6.1.0",
    "actions/setup-node@48b55a011bda9f5d6aeb4c2d9c7362e8dae4041e": "v6.4.0",
    "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1": "v6.3.0",
    "aquasecurity/trivy-action@ed142fd0673e97e23eac54620cfb913e5ce36c25": "v0.36.0",
    "github/codeql-action/analyze@c54b30b7df092240050e69945842bc67aee0f0f4": "v4.37.3",
    "github/codeql-action/init@c54b30b7df092240050e69945842bc67aee0f0f4": "v4.37.3",
    "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093": "v4.3.0",
    "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02": "v4.6.2",
}


def _workflow() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _command_block(workflow: str, start: str, end: str) -> str:
    return workflow.split(start, maxsplit=1)[1].split(end, maxsplit=1)[0]


def test_required_regressions_are_in_the_pytest_and_ruff_gates() -> None:
    workflow = _workflow()
    ruff_block = _command_block(workflow, "python -m ruff check", "- name: Security regression tests")
    pytest_block = _command_block(workflow, "python -m pytest -q", "python scripts/check-telemetry-privacy.py")

    missing_pytest = sorted(REQUIRED_REGRESSION_TESTS.difference(pytest_block.split()))
    missing_ruff = sorted(REQUIRED_RUFF_BOUNDARIES.difference(ruff_block.split()))

    assert not missing_pytest, f"Required security tests missing from pytest gate: {missing_pytest}"
    assert not missing_ruff, f"Security boundaries missing from Ruff gate: {missing_ruff}"


def test_actions_are_immutably_pinned() -> None:
    workflow = "\n".join(
        (
            _workflow(),
            CODEQL_WORKFLOW_PATH.read_text(encoding="utf-8"),
            RELEASE_EVIDENCE_WORKFLOW_PATH.read_text(encoding="utf-8"),
        )
    )
    action_lines = re.findall(
        r"^[ \t]*-?[ \t]*uses:[ \t]*([^\s#]+)(?:[ \t]+#[ \t]*(\S+))?",
        workflow,
        re.MULTILINE,
    )
    references = {reference for reference, _comment in action_lines}

    unpinned = {
        reference
        for reference in references
        if not re.fullmatch(r"[^@]+@[0-9a-f]{40}", reference)
    }
    assert not unpinned

    for reference, version_comment in action_lines:
        if re.fullmatch(r"[^@]+@[0-9a-f]{40}", reference):
            assert re.fullmatch(r"v\d+\.\d+\.\d+", version_comment), (
                f"Pinned action must retain its human-readable release comment: {reference}"
            )

    for reference, expected_version in PINNED_ACTIONS.items():
        matches = [comment for candidate, comment in action_lines if candidate == reference]
        assert matches, f"Pinned action is absent: {reference}"
        assert all(comment == expected_version for comment in matches)


def test_shogun_server_failure_diagnostics_tolerate_an_early_build_failure() -> None:
    workflow = _workflow()
    logs_block = _command_block(
        workflow,
        "- name: Shogun Server logs",
        "- name: Clean up Shogun Server",
    )
    cleanup_block = workflow.split("- name: Clean up Shogun Server", maxsplit=1)[1]

    assert "if [ -f .env.server ]; then" in logs_block
    assert "docker compose --env-file .env.server -f docker-compose.server.yml logs || true" in logs_block
    assert "if [ -f .env.server ]; then" in cleanup_block
    assert "docker compose --env-file .env.server -f docker-compose.server.yml down --volumes || true" in cleanup_block
