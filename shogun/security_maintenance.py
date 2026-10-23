"""Shared eMudhra maintenance policy; bootstrap works before app dependencies exist.

Run with the intended interpreter: python shogun/security_maintenance.py bootstrap.
The direct wheel hashes are published by the Python release team and PyPI.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import os
import re
import shutil
import ssl
import subprocess
import sys
from pathlib import Path

PIP_MINIMUM = "26.2.2"
CERTIFI_MINIMUM = "2026.10.19"
PIP_WHEEL = (
    "https://files.pythonhosted.org/packages/3f/06/"
    "3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/"
    "pip-26.2.2-py3-none-any.whl"
    "#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"
)
CERTIFI_WHEEL = (
    "https://files.pythonhosted.org/packages/c4/51/"
    "29046e48f693c54e5b7412216d447a1d8362c9653148d98c02cdf65fa733/"
    "certifi-2026.10.19-py3-none-any.whl"
    "#sha256=42d35340cc5b9ba78e818ddbff0c5b1c2b779de448a340fd1b989f5fa8670e1b"
)
NODE_MINIMUMS = {22: (22, 23, 4), 24: (24, 22, 1)}
UNSAFE_PEM_CERTIFICATES = frozenset(
    {
        "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b",  # emSign G3
        "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4",  # alternate AAA path
        # Known affected TLS intermediates, including their AAA cross-signs.
        "0164d7ceae5bb909c272af151ff44b1177ae9b47d9424b94f1d9558c30934d19",
        "42c4accd12c4f59597925e1a08a7a90102608543809308d50ec427e118ba1493",
        "432ec25f0d28de9006d97bf752f17bbb2cd41f669933fcb072d9a1148d0261f3",
        "45a883f349aedfd5f3a649b5498ffb121712ba8b448f3f2a91dbc5a766fcddbe",
        "579480aea166290bd3c643589e795fc0d0e54e86505d180f1dff99efd3199512",
        "5f1ded4dd590af74631290cf073b122a2aac6a1fa479778a0bd43579bd832699",
        "62b7f9868263f72f6911fc78ceaf72c1979158b7368bf648683bb2aa39b02e72",
        "7485b51c0ed192878fa1d2f948fb529ae1842cc5086c4b67f7be5b2039de9489",
        "98b896625c0c230adeec3eb2cf6aad5001ecf9156a68644e82374ce5833bc25b",
        "cb6e15165ac802e9b3f993f16c25d41f4e81c21ebde71ae1b012ac00bf9c7c3f",
        "e7568fe6e12331f4fd7de61da4c7559d0f8eb192a218d4741a3ba75184333838",
        "fd9d5c2dbbd4995ab69b8d50c439d9527b00529199c2fd01b2174eb58f07021f",
    }
)


class SecurityMaintenanceError(RuntimeError):
    """A required maintenance prerequisite is unavailable or unsafe."""


def release_at_least(installed: str, minimum: str) -> bool:
    """Compare stable numeric releases; never accept a prerelease as its final.

    These tools publish numeric stable releases. Reject unknown/local/prerelease
    formats explicitly instead of guessing security equivalence or downgrading.
    """
    if not re.fullmatch(r"\d+(?:\.\d+)*", installed):
        raise SecurityMaintenanceError("A non-stable package version requires vendor security verification.")
    current = tuple(int(part) for part in installed.split("."))
    required = tuple(int(part) for part in minimum.split("."))
    width = max(len(current), len(required))
    return current + (0,) * (width - len(current)) >= required + (0,) * (width - len(required))


def package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "0"


def check_python_security(*, include_system: bool = True, require_installer: bool = True) -> None:
    required = [("certifi", CERTIFI_MINIMUM)]
    if require_installer:
        required.append(("pip", PIP_MINIMUM))
    for name, minimum in required:
        if not release_at_least(package_version(name), minimum):
            raise SecurityMaintenanceError(
                f"{name}>={minimum} is required. Run the security bootstrap with this installation's Python."
            )
    import certifi

    bundles = [certifi.where()]
    if require_installer:
        import pip._vendor.certifi as pip_certifi

        bundles.append(pip_certifi.where())
    for bundle in bundles:
        check_pem_bundle(Path(bundle))
    for key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "PIP_CERT"):
        if os.environ.get(key):
            check_pem_trust_path(Path(os.environ[key]))
    if os.environ.get("SSL_CERT_DIR"):
        for directory in os.environ["SSL_CERT_DIR"].split(os.pathsep):
            check_pem_trust_path(Path(directory))
    if include_system and sys.platform.startswith("linux"):
        # pip's Linux truststore backend also loads the effective OpenSSL system
        # store. A corrected vendored bundle alone cannot remove those anchors.
        defaults = ssl.get_default_verify_paths()
        for location in (defaults.cafile, defaults.capath):
            if location:
                check_pem_trust_path(Path(location))


def check_pem_trust_path(path: Path) -> None:
    if not path.is_dir():
        check_pem_bundle(path)
        return
    # OpenSSL capath lookup uses hashed names, not arbitrary archived PEM files
    # or CRL entries in the same directory. Preserve those unrelated files.
    for bundle in path.iterdir():
        if bundle.is_file() and re.fullmatch(r"[0-9a-fA-F]{8}\.\d+", bundle.name):
            check_pem_bundle(bundle)


def check_pem_bundle(path: Path) -> None:
    """Check PEM trust anchors without rewriting private/enterprise CA material."""
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cafile=str(path))
    except (OSError, ssl.SSLError) as exc:
        raise SecurityMaintenanceError(
            "A certificate bundle could not be verified; review the CA configuration."
        ) from exc
    if any(
        hashlib.sha256(cert).hexdigest() in UNSAFE_PEM_CERTIFICATES for cert in context.get_ca_certs(binary_form=True)
    ):
        raise SecurityMaintenanceError(
            "A certificate bundle retains an affected public trust path; correct it before updating."
        )


def bootstrap_python(*, allow_system: bool = False) -> None:
    """Repair only the selected environment, using authenticated direct wheels."""
    if sys.prefix == sys.base_prefix and not allow_system:
        raise SecurityMaintenanceError("Select the application virtual environment before bootstrapping.")
    for name, minimum, wheel in (
        ("pip", PIP_MINIMUM, PIP_WHEEL),
        ("certifi", CERTIFI_MINIMUM, CERTIFI_WHEEL),
    ):
        if release_at_least(package_version(name), minimum):
            continue
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "install",
                "--no-index",
                "--no-deps",
                "--upgrade",
                f"{name} @ {wheel}",
            ],
            check=False,
            timeout=180,
        )
        if result.returncode:
            raise SecurityMaintenanceError(f"Authenticated {name} bootstrap failed; stop maintenance.")
        importlib.invalidate_caches()
    check_python_security()


def node_version_supported(value: str) -> bool:
    if not re.fullmatch(r"v?\d+\.\d+\.\d+", value):
        return False
    release = tuple(int(part) for part in value.removeprefix("v").split("."))
    minimum = NODE_MINIMUMS.get(release[0])
    return minimum is not None and release >= minimum


def check_node(executable: str | Path) -> Path:
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SecurityMaintenanceError("The selected Node.js runtime could not be checked.") from exc
    if result.returncode or not node_version_supported(result.stdout.strip()):
        raise SecurityMaintenanceError("Node.js 22.23.4+ (22.x) or 24.22.1+ (24.x) is required.")
    return Path(executable).resolve()


def node_environment() -> dict[str, str]:
    """Use an app-managed runtime when present, preserving explicit CA settings."""
    environment = os.environ.copy()
    managed = Path(sys.prefix) / "node-runtime" / ("node.exe" if os.name == "nt" else "bin/node")
    selected = str(managed) if managed.is_file() else shutil.which("node")
    if selected is None:
        raise SecurityMaintenanceError("Install a corrected supported Node.js runtime before this operation.")
    node = check_node(selected)
    environment["PATH"] = str(node.parent) + os.pathsep + environment.get("PATH", "")
    # Playwright supports a separate driver selection. Validate explicit operator
    # choices too, so a patched host cannot mask an affected driver override.
    driver = environment.get("PLAYWRIGHT_NODEJS_PATH")
    environment["PLAYWRIGHT_NODEJS_PATH"] = str(check_node(driver) if driver else node)
    if environment.get("NODE_TLS_REJECT_UNAUTHORIZED") == "0":
        raise SecurityMaintenanceError("Restore Node.js certificate verification before this operation.")
    return environment


def configure_playwright_node() -> None:
    environment = node_environment()
    os.environ["PLAYWRIGHT_NODEJS_PATH"] = environment["PLAYWRIGHT_NODEJS_PATH"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("bootstrap", "check", "node"))
    parser.add_argument("--allow-system", action="store_true", help="Only for a managed CI/container interpreter")
    parser.add_argument("--node", action="store_true", help="Also check the selected Node/Playwright runtime")
    parser.add_argument(
        "--runtime-only", action="store_true", help="Check immutable runtime trust without installer tools"
    )
    args = parser.parse_args()
    if args.runtime_only and args.action != "check":
        parser.error("--runtime-only is only valid for the read-only check action")
    try:
        if args.action == "bootstrap":
            bootstrap_python(allow_system=args.allow_system)
        elif args.action == "check":
            check_python_security(require_installer=not args.runtime_only)
        if args.node or args.action == "node":
            node_environment()
    except (SecurityMaintenanceError, subprocess.TimeoutExpired) as exc:
        print(f"Security maintenance failed: {exc}", file=sys.stderr)
        return 1
    print("Security maintenance prerequisites verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
