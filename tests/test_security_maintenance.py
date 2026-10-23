"""Maintenance policy, authenticated bootstrap and actual incident-chain regressions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import ssl
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import certifi
import pytest

from shogun import security_maintenance as maintenance

FIXTURES = Path(__file__).parent / "fixtures/emudhra"


@pytest.mark.parametrize("version", ["22.23.4", "22.24.0", "24.22.1", "v24.23.0"])
def test_accepts_corrected_supported_node_lines(version):
    assert maintenance.node_version_supported(version)


@pytest.mark.parametrize(
    "version",
    [
        "22.12.0",
        "22.23.3",
        "24.16.0",
        "24.22.0",
        "23.99.0",
        "25.0.0",
        "26.12.1",
        "24.22.1-rc.1",
        "24.22",
        "unknown",
    ],
)
def test_rejects_affected_unsupported_or_unverified_node(version):
    assert not maintenance.node_version_supported(version)


def test_package_versions_compare_numerically_and_keep_newer_releases():
    assert maintenance.release_at_least("26.10", "26.2.2")
    assert maintenance.release_at_least("26.2.2.0", "26.2.2")
    assert not maintenance.release_at_least("26.2.1", "26.2.2")
    with pytest.raises(maintenance.SecurityMaintenanceError):
        maintenance.release_at_least("26.2.2rc1", "26.2.2")


def test_bootstrap_authenticates_both_wheels_and_preserves_newer_versions(monkeypatch):
    versions = {"pip": "25.2", "certifi": "2026.2.25"}
    monkeypatch.setattr(sys, "base_prefix", "different-base")
    monkeypatch.setattr(maintenance, "package_version", versions.__getitem__)
    monkeypatch.setattr(maintenance, "check_python_security", lambda: None)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert command[0] == sys.executable
        assert "--no-index" in command and "--no-deps" in command
        assert "--no-cache-dir" in command and kwargs["timeout"] == 180
        name = command[-1].split(" @ ")[0]
        assert "#sha256=" in command[-1]
        versions[name] = {"pip": "26.2.2", "certifi": "2026.10.19"}[name]
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(maintenance.subprocess, "run", run)
    maintenance.bootstrap_python()
    assert [command[-1] for command in calls] == [
        "pip @ " + maintenance.PIP_WHEEL,
        "certifi @ " + maintenance.CERTIFI_WHEEL,
    ]
    versions.update({"pip": "27.0", "certifi": "2027.1.1"})
    calls.clear()
    maintenance.bootstrap_python()
    assert calls == []


def test_bootstrap_failure_stops_before_subsequent_packages(monkeypatch):
    monkeypatch.setattr(sys, "base_prefix", "different-base")
    monkeypatch.setattr(maintenance, "package_version", lambda _: "0")
    calls = []
    monkeypatch.setattr(
        maintenance.subprocess, "run", lambda command, **_: calls.append(command) or SimpleNamespace(returncode=1)
    )
    with pytest.raises(maintenance.SecurityMaintenanceError, match="pip bootstrap failed"):
        maintenance.bootstrap_python()
    assert len(calls) == 1


def test_bootstrap_refuses_unintended_global_python(monkeypatch):
    monkeypatch.setattr(sys, "base_prefix", sys.prefix)
    with pytest.raises(maintenance.SecurityMaintenanceError, match="virtual environment"):
        maintenance.bootstrap_python()


def test_runtime_trust_check_allows_an_immutable_image_without_installer_tools(monkeypatch):
    monkeypatch.setattr(
        maintenance, "package_version", lambda name: maintenance.CERTIFI_MINIMUM if name == "certifi" else "0"
    )
    with pytest.raises(maintenance.SecurityMaintenanceError, match="pip>="):
        maintenance.check_python_security(include_system=False)
    maintenance.check_python_security(include_system=False, require_installer=False)
    monkeypatch.setattr(certifi, "where", lambda: str(FIXTURES / "emsign-g3.crt"))
    with pytest.raises(maintenance.SecurityMaintenanceError, match="affected public trust path"):
        maintenance.check_python_security(include_system=False, require_installer=False)


@pytest.mark.parametrize("action", ["bootstrap", "node"])
def test_runtime_only_flag_cannot_bypass_installer_bootstrap(action):
    result = subprocess.run(
        [sys.executable, maintenance.__file__, action, "--runtime-only"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 2
    assert "only valid for the read-only check" in result.stderr


def test_direct_entrypoint_checks_trust_before_environment_or_restore_changes(monkeypatch):
    from shogun import __main__ as entrypoint

    def reject_trust(**kwargs):
        assert kwargs == {"require_installer": False}
        raise maintenance.SecurityMaintenanceError("unsafe trust fixture")

    monkeypatch.setattr(sys, "argv", ["shogun"])
    monkeypatch.setattr(entrypoint, "_reexec_in_project_venv", lambda: None)
    monkeypatch.setattr(entrypoint, "_ensure_env_file", lambda: pytest.fail("environment changed before trust check"))
    monkeypatch.setattr(maintenance, "check_python_security", reject_trust)
    with pytest.raises(maintenance.SecurityMaintenanceError, match="unsafe trust fixture"):
        entrypoint.main()


@pytest.mark.asyncio
async def test_direct_asgi_startup_checks_trust_before_database_migrations(monkeypatch):
    from fastapi import FastAPI

    import shogun.app as application

    def reject_trust(**kwargs):
        assert kwargs == {"require_installer": False}
        raise maintenance.SecurityMaintenanceError("unsafe trust fixture")

    monkeypatch.setattr(application, "check_python_security", reject_trust)
    monkeypatch.setattr(application, "_upgrade_database_schema", lambda: pytest.fail("database migration started"))
    with pytest.raises(maintenance.SecurityMaintenanceError, match="unsafe trust fixture"):
        async with application.lifespan(FastAPI()):
            pytest.fail("unsafe application started")


def test_managed_node_is_used_for_npm_and_playwright_without_losing_ca_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "prefix", str(tmp_path))
    node = tmp_path / "node-runtime" / ("node.exe" if os.name == "nt" else "bin/node")
    node.parent.mkdir(parents=True)
    node.touch()
    monkeypatch.delenv("PLAYWRIGHT_NODEJS_PATH", raising=False)
    monkeypatch.setenv("NODE_EXTRA_CA_CERTS", "private-enterprise-ca.crt")
    monkeypatch.setattr(maintenance, "check_node", lambda executable: Path(executable).resolve())
    environment = maintenance.node_environment()
    assert environment["PATH"].split(os.pathsep)[0] == str(node.parent)
    assert environment["PLAYWRIGHT_NODEJS_PATH"] == str(node)
    assert environment["NODE_EXTRA_CA_CERTS"] == "private-enterprise-ca.crt"


def test_an_affected_explicit_playwright_override_cannot_hide_behind_patched_host(monkeypatch):
    monkeypatch.setenv("PLAYWRIGHT_NODEJS_PATH", "old-driver")

    def check_node(executable):
        if str(executable) == "old-driver":
            raise maintenance.SecurityMaintenanceError("Affected driver")
        return Path(executable)

    monkeypatch.setattr(maintenance, "check_node", check_node)
    with pytest.raises(maintenance.SecurityMaintenanceError, match="Affected driver"):
        maintenance.node_environment()


def test_corrected_bundle_passes_and_affected_custom_bundle_is_rejected_without_editing():
    maintenance.check_pem_bundle(Path(certifi.where()))
    affected = FIXTURES / "emsign-g3.crt"
    before = affected.read_bytes()
    with pytest.raises(maintenance.SecurityMaintenanceError, match="affected public trust path"):
        maintenance.check_pem_bundle(affected)
    assert affected.read_bytes() == before


def test_custom_trust_cannot_accept_an_affected_intermediate_as_an_anchor(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding

    for path in FIXTURES.glob("*we-have-a-problem.com.crt"):
        intermediate = x509.load_pem_x509_certificates(path.read_bytes())[1]
        custom = tmp_path / "custom-ca.crt"
        original = intermediate.public_bytes(Encoding.PEM)
        custom.write_bytes(original)
        with pytest.raises(maintenance.SecurityMaintenanceError, match="affected public trust path"):
            maintenance.check_pem_bundle(custom)
        assert custom.read_bytes() == original


def _openssl() -> str:
    binary = shutil.which("openssl")
    if not binary and os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/usr/bin/openssl.exe"
        binary = str(candidate) if candidate.is_file() else None
    if not binary:
        pytest.skip("OpenSSL executable is required for offline incident fixture verification")
    return binary


def test_all_incident_chains_are_rejected_by_both_corrected_python_bundles():
    import pip._vendor.certifi as pip_certifi

    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["chains"]) == 14
    for entry in manifest["chains"]:
        chain = FIXTURES / entry["file"]
        assert hashlib.sha256(chain.read_bytes()).hexdigest() == entry["sha256"]
        for bundle in (certifi.where(), pip_certifi.where()):
            result = subprocess.run(
                [
                    _openssl(),
                    "verify",
                    "-no-CApath",
                    "-no-CAstore",
                    "-CAfile",
                    bundle,
                    "-attime",
                    str(entry["verification_time"]),
                    "-purpose",
                    "sslserver",
                    "-verify_hostname",
                    entry["hostname"],
                    "-untrusted",
                    str(chain),
                    str(chain),
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            assert result.returncode != 0, entry["hostname"]
            assert "unable to get local issuer certificate" in result.stderr, result.stderr


def test_direct_incident_fixtures_reach_trust_decision_with_original_root_positive_control():
    """Fixed time excludes expiry/hostname errors; no machine clock or store changes."""
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["chains"]:
        if "-aaa-" in entry["hostname"]:
            continue
        chain = FIXTURES / entry["file"]
        result = subprocess.run(
            [
                _openssl(),
                "verify",
                "-no-CApath",
                "-no-CAstore",
                "-CAfile",
                str(FIXTURES / "emsign-g3.crt"),
                "-attime",
                str(entry["verification_time"]),
                "-purpose",
                "sslserver",
                "-verify_hostname",
                entry["hostname"],
                "-untrusted",
                str(chain),
                str(chain),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "code,expected",
    [
        (20, "rejected"),
        (23, "rejected"),
        (0x80092010, "rejected"),
        (10, "inconclusive"),
        (62, "inconclusive"),
        (0x80092013, "inconclusive"),
    ],
)
def test_live_verifier_distinguishes_distrust_from_expiry_hostname_and_offline_revocation(code, expected):
    from scripts.verify_tls_incident import certificate_outcome

    verification = ssl.SSLCertVerificationError("localized verifier message")
    verification.verify_code = code
    wrapped = RuntimeError("client wrapper")
    wrapped.__context__ = verification
    assert certificate_outcome(wrapped) == {"tls": expected, "reason": f"certificate-code-{code}"}


def test_node_archive_digest_failure_does_not_extract_anything(tmp_path):
    from scripts.install_security_node import extract_authenticated_archive

    archive = tmp_path / "node.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("node/node.exe", b"synthetic executable")
    destination = tmp_path / "output"
    with pytest.raises(maintenance.SecurityMaintenanceError, match="authentication failed"):
        extract_authenticated_archive(archive, destination, "0" * 64)
    assert not destination.exists()


def test_authenticated_node_archive_cannot_escape_staging(tmp_path):
    from scripts.install_security_node import extract_authenticated_archive

    archive = tmp_path / "node.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape", b"synthetic content")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with pytest.raises(maintenance.SecurityMaintenanceError, match="Unsafe path"):
        extract_authenticated_archive(archive, tmp_path / "output", digest)
    assert not (tmp_path / "escape").exists()


def test_linux_native_store_cannot_reintroduce_affected_roots(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        maintenance,
        "package_version",
        lambda name: {
            "pip": maintenance.PIP_MINIMUM,
            "certifi": maintenance.CERTIFI_MINIMUM,
        }[name],
    )
    monkeypatch.setattr(
        maintenance.ssl,
        "get_default_verify_paths",
        lambda: SimpleNamespace(
            cafile=str(FIXTURES / "emsign-g3.crt"),
            capath=None,
        ),
    )
    maintenance.check_python_security(include_system=False)
    with pytest.raises(maintenance.SecurityMaintenanceError, match="affected public trust path"):
        maintenance.check_python_security()
