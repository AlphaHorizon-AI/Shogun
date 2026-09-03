#!/usr/bin/env python3
"""Run the deterministic Security hardening checks locally or in CI."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

RUFF_PATHS = (
    "shogun/api/a2a.py",
    "shogun/api/control_plane_auth.py",
    "shogun/api/infrastructure_auth.py",
    "shogun/api/email.py",
    "shogun/api/setup.py",
    "shogun/api/ronin.py",
    "shogun/api/security.py",
    "shogun/api/telemetry.py",
    "shogun/api/updates.py",
    "shogun/config.py",
    "shogun/edition.py",
    "shogun/integrations/a2a_client.py",
    "shogun/services/a2a_crypto.py",
    "shogun/services/calendar_service.py",
    "shogun/services/cascade_retrieval.py",
    "shogun/services/chat_sync_service.py",
    "shogun/services/comms_permissions.py",
    "shogun/services/email_service.py",
    "shogun/services/request_context.py",
    "shogun/services/startup_notices.py",
    "shogun/services/ssrf_guard.py",
    "shogun/services/telegram_poller.py",
    "shogun/services/provider_credentials.py",
    "shogun/services/release_metadata.py",
    "shogun/services/college_telemetry.py",
    "shogun/services/event_logger.py",
    "shogun/services/update_checker.py",
    "shogun/ronin/core/audit_logger.py",
    "shogun/ronin/core/approval_gate.py",
    "shogun/ronin/core/action_router.py",
    "shogun/ronin/core/capabilities_registry.py",
    "shogun/ronin/core/posture_guard.py",
    "shogun/ronin/core/ronin_controller.py",
    "shogun/ronin/policies/ronin_policy_schema.py",
    "shogun/schemas/ronin.py",
    "shogun/setup_link.py",
    "shogun/telemetry",
    "shogun/telemetry/payload.py",
    "telemetry_service",
    "scripts/generate_release_evidence.py",
    "scripts/verify_security_ci.py",
    "scripts/write_release_metadata_evidence.py",
)

PYTEST_PATHS = (
    "tests/test_ssrf_guard.py",
    "tests/test_install_telemetry.py",
    "tests/test_telemetry_ingestion.py",
    "tests/test_red_team_hardening.py",
    "tests/test_calendar_permissions.py",
    "tests/test_security_punch_list.py",
    "tests/test_cli_environment.py",
    "tests/test_restart_service.py",
    "tests/test_college_telemetry.py",
    "tests/test_cascade_retrieval.py",
    "tests/test_chat_sync.py",
    "tests/test_guide_incident_reporting.py",
    "tests/test_installer_release_provenance.py",
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
    "tests/test_update_provenance.py",
    "tests/test_update_checker.py",
    "tests/test_updates.py",
    "tests/test_yellow_label_edition.py",
)


def _run(
    command: list[str],
    *,
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> None:
    print(f"+ {shlex.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def _npm_command(*arguments: str) -> list[str]:
    npm = shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm is required for frontend verification")
    if os.name == "nt":
        command_processor = os.environ.get("COMSPEC", "cmd.exe")
        return [command_processor, "/d", "/s", "/c", "call", npm, *arguments]
    return [npm, *arguments]


def verify_backend() -> None:
    python = sys.executable
    _run([python, "scripts/sync_guide_translations.py", "--check"])
    # Match a clean CI checkout and avoid loading an operator's local .env.
    import_env = os.environ.copy()
    import_env["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(ROOT), import_env.get("PYTHONPATH")) if path
    )
    import_env["SHOGUN_SKIP_ENV_FILE"] = "true"
    with tempfile.TemporaryDirectory(prefix="shogun-ci-import-") as import_dir:
        _run(
            [python, "-c", "import shogun.app"],
            cwd=Path(import_dir),
            env=import_env,
        )
    _run([
        python,
        "-m",
        "ruff",
        "check",
        "--select",
        "E,F,I,N,W,UP",
        "--ignore",
        "B008",
        *RUFF_PATHS,
        *PYTEST_PATHS,
    ])
    with tempfile.TemporaryDirectory(prefix="shogun-pytest-") as pytest_dir:
        pytest_base = Path(pytest_dir) / "run"
        _run(
            [
                python,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "--basetemp",
                str(pytest_base),
                *PYTEST_PATHS,
            ],
            env=import_env,
        )
    _run([python, "scripts/check-telemetry-privacy.py"], env=import_env)


def verify_dependency_audit() -> None:
    _run(_npm_command("run", "audit:security"), cwd=FRONTEND)


def verify_frontend() -> None:
    _run(_npm_command("run", "lint:security"), cwd=FRONTEND)
    _run(_npm_command("run", "build"), cwd=FRONTEND)
    _run(_npm_command("run", "test:security"), cwd=FRONTEND)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--all", action="store_const", const="all", dest="mode")
    modes.add_argument("--backend", action="store_const", const="backend", dest="mode")
    modes.add_argument(
        "--dependency-audit",
        action="store_const",
        const="dependency-audit",
        dest="mode",
    )
    modes.add_argument("--frontend", action="store_const", const="frontend", dest="mode")
    args = parser.parse_args()

    if args.mode in {"all", "backend"}:
        verify_backend()
    if args.mode in {"all", "dependency-audit"}:
        verify_dependency_audit()
    if args.mode in {"all", "frontend"}:
        verify_frontend()


if __name__ == "__main__":
    main()
