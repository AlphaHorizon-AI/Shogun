"""Static guards for the required security-hardening CI boundary."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "security-hardening.yml"
CODEQL_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "codeql.yml"
RELEASE_EVIDENCE_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "release-evidence.yml"
VERIFY_SCRIPT_PATH = ROOT / "scripts" / "verify_security_ci.py"
PRE_PUSH_HOOK_PATH = ROOT / ".githooks" / "pre-push"

REQUIRED_REGRESSION_TESTS = {
    "tests/test_college_telemetry.py",
    "tests/test_cascade_retrieval.py",
    "tests/test_chat_sync.py",
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
    "tests/test_telemetry_ingestion.py",
    "tests/test_update_checker.py",
    "tests/test_update_provenance.py",
    "tests/test_updates.py",
    "tests/test_yellow_label_edition.py",
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
} | REQUIRED_REGRESSION_TESTS

APPROVED_ACTIONS = {
    "actions/checkout",
    "actions/download-artifact",
    "actions/setup-node",
    "actions/setup-python",
    "actions/upload-artifact",
    "aquasecurity/trivy-action",
    "github/codeql-action/analyze",
    "github/codeql-action/init",
}


def _workflow() -> str:
    return WORKFLOW_PATH.read_text(encoding="utf-8")


def _command_block(workflow: str, start: str, end: str) -> str:
    return workflow.split(start, maxsplit=1)[1].split(end, maxsplit=1)[0]


def test_required_regressions_are_in_the_pytest_and_ruff_gates() -> None:
    workflow = _workflow()
    verification_script = VERIFY_SCRIPT_PATH.read_text(encoding="utf-8")

    missing_pytest = sorted(
        path for path in REQUIRED_REGRESSION_TESTS if f'"{path}"' not in verification_script
    )
    missing_ruff = sorted(
        path for path in REQUIRED_RUFF_BOUNDARIES if f'"{path}"' not in verification_script
    )

    assert not missing_pytest, f"Required security tests missing from pytest gate: {missing_pytest}"
    assert not missing_ruff, f"Security boundaries missing from Ruff gate: {missing_ruff}"
    assert "python scripts/verify_security_ci.py --backend" in workflow
    assert "python ../scripts/verify_security_ci.py --frontend" in workflow
    assert "name: Dependency security - Tenshu" in workflow
    assert "run: npm run audit:security" in workflow


def _action_policy_errors(workflow: str) -> list[str]:
    action_lines = re.findall(
        r"^[ \t]*-?[ \t]*uses:[ \t]*([^\s#]+)(?:[ \t]+#[ \t]*(\S+))?",
        workflow,
        re.MULTILINE,
    )
    errors: list[str] = []
    action_names: set[str] = set()

    for reference, version_comment in action_lines:
        match = re.fullmatch(r"([^@]+)@([0-9a-f]{40})", reference)
        if match is None:
            errors.append(f"Action is not pinned to a full commit SHA: {reference}")
            continue
        action_names.add(match.group(1))
        if re.fullmatch(r"v\d+\.\d+\.\d+", version_comment) is None:
            errors.append(
                f"Pinned action must retain its release comment: {reference}"
            )

    for action_name in sorted(action_names.difference(APPROVED_ACTIONS)):
        errors.append(f"Action is not approved: {action_name}")
    for action_name in sorted(APPROVED_ACTIONS.difference(action_names)):
        errors.append(f"Approved action is absent: {action_name}")
    return errors


def test_actions_are_immutably_pinned() -> None:
    workflow = "\n".join(
        (
            _workflow(),
            CODEQL_WORKFLOW_PATH.read_text(encoding="utf-8"),
            RELEASE_EVIDENCE_WORKFLOW_PATH.read_text(encoding="utf-8"),
        )
    )
    assert not _action_policy_errors(workflow)


def test_action_policy_accepts_dependabot_sha_rotation() -> None:
    rotated_workflow = "\n".join(
        f"- uses: {action_name}@{'f' * 40} # v99.0.0"
        for action_name in sorted(APPROVED_ACTIONS)
    )
    assert not _action_policy_errors(rotated_workflow)


def test_pre_push_hook_runs_the_shared_security_verification() -> None:
    hook = PRE_PUSH_HOOK_PATH.read_text(encoding="utf-8")
    assert 'scripts/verify_security_ci.py --all' in hook


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
