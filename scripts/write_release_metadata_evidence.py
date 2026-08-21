#!/usr/bin/env python3
"""Write canonical, non-sensitive release provenance for an archive install.

This helper intentionally depends only on the Python standard library and the
installed Shogun source tree so the standalone desktop installers can invoke it
before application dependencies are installed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def _manifest(root: Path) -> dict[str, Any]:
    payload = json.loads((root / "version.json").read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("version.json must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--git-sha", required=True)
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    sys.path.insert(0, str(root))
    from shogun.services.release_metadata import write_release_metadata_evidence

    destination = write_release_metadata_evidence(root, _manifest(root), args.git_sha)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
