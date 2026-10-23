"""Opt-in credential-free TLS probes for the published eMudhra diagnostic hosts.

No packages are installed and no application data or native trust stores are
changed. A network error is INCONCLUSIVE, never a successful distrust result.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import ssl
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shogun.security_maintenance import (  # noqa: E402
    SecurityMaintenanceError,
    check_python_security,
    node_environment,
)

NODE_PROBE = """
const https = require('node:https');
const target = process.argv[1];
const request = https.request(target, {method: 'HEAD', rejectUnauthorized: true}, response => {
  response.resume();
  console.log(JSON.stringify({tls: 'accepted', status: response.statusCode}));
});
request.setTimeout(10000, () => request.destroy(new Error('network-timeout')));
request.on('error', error => console.log(JSON.stringify({tls: 'error', reason: error.code || 'network-error'})));
request.end();
"""


def certificate_outcome(error: BaseException) -> dict:
    """Follow client wrappers to the verifier's numeric, locale-independent code."""
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            code = getattr(current, "verify_code", None)
            trust_errors = {2, 18, 19, 20, 21, 23, 0x800B0109, 0x800B010A, 0x800B010C, 0x800B0111, 0x80092010}
            return {"tls": "rejected" if code in trust_errors else "inconclusive", "reason": f"certificate-code-{code}"}
        for nested in (current.__cause__, current.__context__, getattr(current, "reason", None), *current.args):
            if isinstance(nested, BaseException):
                pending.append(nested)
    return {"tls": "inconclusive", "reason": type(error).__name__}


def _python_probe(client: str, url: str) -> dict:
    if client == "httpx":
        import httpx

        try:
            with httpx.Client(trust_env=False, timeout=10, follow_redirects=False) as session:
                response = session.head(url)
                return {"tls": "accepted", "status": response.status_code}
        except httpx.TransportError as exc:
            return certificate_outcome(exc)

    # Use the installed pip CLI's own combined native/certifi context. Disable
    # auth, netrc, proxy discovery and keyring; these are diagnostic HEAD requests.
    from pip._internal.cli.index_command import _create_truststore_ssl_context
    from pip._internal.exceptions import DiagnosticPipError
    from pip._internal.network.session import PipSession
    from pip._vendor.requests.exceptions import RequestException, SSLError

    try:
        with PipSession(ssl_context=_create_truststore_ssl_context(), retries=0) as session:
            session.trust_env = False
            session.auth = None
            response = session.head(url, timeout=10, allow_redirects=False)
            return {"tls": "accepted", "status": response.status_code}
    except (SSLError, RequestException, DiagnosticPipError) as exc:
        return certificate_outcome(exc)


def _node_probe(executable: str, environment: dict[str, str], url: str) -> dict:
    result = subprocess.run(
        [executable, "-e", NODE_PROBE, url],
        env=environment,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    if result.returncode:
        return {"tls": "inconclusive", "reason": "node-probe-failed"}
    outcome = json.loads(result.stdout)
    if outcome["tls"] == "error":
        certificate_errors = {
            "UNABLE_TO_GET_ISSUER_CERT_LOCALLY",
            "UNABLE_TO_VERIFY_LEAF_SIGNATURE",
            "CERT_REVOKED",
            "ERR_TLS_CERT_ALTNAME_INVALID",
            "CERT_HAS_EXPIRED",
            "DEPTH_ZERO_SELF_SIGNED_CERT",
        }
        reason = outcome["reason"]
        # Hostname and expiry failures do not prove incident distrust.
        conclusive = reason in certificate_errors - {"ERR_TLS_CERT_ALTNAME_INVALID", "CERT_HAS_EXPIRED"}
        outcome["tls"] = "rejected" if conclusive else "inconclusive"
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", required=True, help="Contact the published diagnostic hosts")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prerequisite_error = None
    try:
        check_python_security()
    except SecurityMaintenanceError as exc:
        # These credential-free diagnostic requests may inspect an affected
        # store. Its failed prerequisite still prevents a successful exit.
        prerequisite_error = str(exc)
    environment = node_environment()
    driver = environment["PLAYWRIGHT_NODEJS_PATH"]
    fixtures = json.loads((Path(__file__).resolve().parents[1] / "tests/fixtures/emudhra/manifest.json").read_text())
    targets = [("https://" + entry["hostname"] + "/", "rejected") for entry in fixtures["chains"]]
    targets.append(("https://pypi.org/", "accepted"))
    checks = []

    def probe(case):
        client, url, expected = case
        try:
            outcome = (
                _node_probe(driver, environment, url) if client == "node-playwright" else _python_probe(client, url)
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            outcome = {"tls": "inconclusive", "reason": type(exc).__name__}
        observed = outcome["tls"]
        verdict = "PASS" if observed == expected else "INCONCLUSIVE" if observed == "inconclusive" else "FAIL"
        return {"client": client, "url": url, "expected": expected, "result": verdict, **outcome}

    cases = [(client, url, expected) for client in ("httpx", "pip", "node-playwright") for url, expected in targets]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as workers:
        checks.extend(workers.map(probe, cases))
    report = {
        "incident": "EMUDHRA-2026-10",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.executable,
        "node_playwright": driver,
        "prerequisite_error": prerequisite_error,
        "checks": checks,
        "limitations": ["Does not verify other installations, native browser trust, or application activation."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    totals = {value: sum(check["result"] == value for check in checks) for value in ("PASS", "FAIL", "INCONCLUSIVE")}
    print(json.dumps(totals))
    return 0 if totals["PASS"] == len(checks) and prerequisite_error is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
