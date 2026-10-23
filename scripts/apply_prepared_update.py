"""Apply an already downloaded pinned release using the normal updater checks."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shogun.security_maintenance import (  # noqa: E402
    SecurityMaintenanceError,
    check_python_security,
    node_environment,
)
from shogun.services.release_metadata import write_release_metadata_evidence  # noqa: E402
from shogun.services.update_installer import (  # noqa: E402
    UpdateInstallError,
    installation_update_lock,
    prepare_and_install_update,
    require_clean_application_checkout,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--git-sha", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[0-9a-f]{40}", args.git_sha):
        parser.error("An immutable full source commit is required.")
    try:
        root, source = args.root.resolve(strict=True), args.source.resolve(strict=True)
        if root == source or source.is_relative_to(root):
            raise UpdateInstallError("Prepare the source outside the installation before applying it.")
        check_python_security()
        environment = node_environment()
        with installation_update_lock(root):
            require_clean_application_checkout(root)
            manifest, count, backup = prepare_and_install_update(source, root, environment, args.git_sha)
            write_release_metadata_evidence(root, manifest, args.git_sha)
        print(f"Installed {count} application files; code recovery material: {backup}")
        print("Restart through the original launcher; activation and TLS verification remain pending.")
    except (SecurityMaintenanceError, UpdateInstallError, OSError) as exc:
        print(f"Update failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
