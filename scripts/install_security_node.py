"""Install an authenticated application-owned Node runtime in the selected venv.

Digests: https://nodejs.org/en/blog/release/v24.22.1 (signed SHASUMS).
Global runtimes, application data and existing compatible runtimes are preserved.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import ssl
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shogun.security_maintenance import (  # noqa: E402
    SecurityMaintenanceError,
    check_node,
    check_python_security,
)

ARCHIVES = {
    ("win32", "amd64"): ("win-x64.zip", "d2046d28c2c3dcd211ac5145c0bf30e2047ef9dfb306693c8c6e2eccd8b95fa5"),
    ("linux", "x86_64"): ("linux-x64.tar.xz", "6c172a9ab6718f7b801fb5a7bd486af2ee5e32758086a04b84fcce2aa77095e6"),
    ("linux", "aarch64"): ("linux-arm64.tar.xz", "dbabf7a1cbf947e6059ffad2c27b80041db97dea1e553b62afdee7f13fca336e"),
    ("darwin", "arm64"): ("darwin-arm64.tar.gz", "89c682593d76cd44233fa53b1563264e7de9cbb189cad169135c5b4fadfbc0a7"),
}


def extract_authenticated_archive(archive: Path, destination: Path, expected_sha256: str) -> None:
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected_sha256:
        raise SecurityMaintenanceError("Node archive authentication failed; nothing was installed.")
    if archive.name.endswith(".zip"):
        with zipfile.ZipFile(archive) as bundle:
            for entry in bundle.infolist():
                if not (destination / entry.filename).resolve().is_relative_to(destination.resolve()):
                    raise SecurityMaintenanceError("Unsafe path in authenticated Node archive.")
            bundle.extractall(destination)
    else:
        if not hasattr(tarfile, "data_filter"):
            raise SecurityMaintenanceError(
                "Use an updated Python with safe tar extraction or a native vendor Node package."
            )
        with tarfile.open(archive) as bundle:
            bundle.extractall(destination, filter="data")


def main() -> int:
    try:
        if sys.prefix == sys.base_prefix:
            raise SecurityMaintenanceError(
                "Run this installer with the intended application virtual environment's Python."
            )
        # This hash-authenticated download uses the corrected certifi bundle
        # explicitly; it can be prepared while a native-store repair is pending.
        check_python_security(include_system=False)
        selected = ARCHIVES.get((sys.platform, platform.machine().lower()))
        if selected is None:
            raise SecurityMaintenanceError("Use a corrected native vendor Node package for this platform.")
        suffix, digest = selected
        filename = "node-v24.22.1-" + suffix
        directory = filename.removesuffix(".zip").removesuffix(".tar.xz").removesuffix(".tar.gz")
        prefix = Path(sys.prefix).resolve()
        destination = prefix / "node-runtime"
        binary = "node.exe" if os.name == "nt" else "bin/node"
        if destination.exists():
            check_node(destination / binary)
            print("Existing corrected application-owned Node retained.")
            return 0
        import certifi

        url = "https://nodejs.org/dist/v24.22.1/" + filename
        with tempfile.TemporaryDirectory(prefix="security-node-", dir=prefix) as temporary:
            staging = Path(temporary).resolve()
            archive = staging / filename
            with urllib.request.urlopen(
                url, context=ssl.create_default_context(cafile=certifi.where()), timeout=120
            ) as response:
                with archive.open("wb") as output:
                    while block := response.read(1024 * 1024):
                        output.write(block)
                        if output.tell() > 150_000_000:
                            raise SecurityMaintenanceError("Node archive exceeds the supported size limit.")
            extract_authenticated_archive(archive, staging, digest)
            extracted = staging / directory
            check_node(extracted / binary)
            # Validate both resolved targets before moving the owned new tree.
            if not extracted.resolve().is_relative_to(prefix) or not destination.resolve().is_relative_to(prefix):
                raise SecurityMaintenanceError("Node installation escaped the selected environment.")
            (extracted / "shogun-runtime.json").write_text(
                json.dumps({"url": url, "sha256": digest, "version": "24.22.1"}, indent=2) + "\n",
                encoding="utf-8",
            )
            extracted.rename(destination)
        print("Authenticated application-owned Node 24.22.1 installed.")
    except (SecurityMaintenanceError, OSError, subprocess.TimeoutExpired, tarfile.TarError, zipfile.BadZipFile) as exc:
        print(f"Node maintenance failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
