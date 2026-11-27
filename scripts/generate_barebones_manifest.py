"""Generate shogun/resources/barebones_manifest.json from the current release tree."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from shogun.services.update_installer import collect_managed_code_files  # noqa: E402


def generate_manifest(root: Path = PROJECT_ROOT) -> Path:
    manifest_rel = "shogun/resources/barebones_manifest.json"
    version_data = json.loads((root / "version.json").read_text(encoding="utf-8"))
    managed = sorted(set(collect_managed_code_files(root)) | {manifest_rel})
    payload = {
        "schema_version": 1,
        "edition": "yellow-label",
        "variant": "barebones-agentflow",
        "version": version_data.get("version"),
        "build": version_data.get("build"),
        "managed_files": managed,
    }
    target = root / manifest_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    out = generate_manifest()
    data = json.loads(out.read_text(encoding="utf-8"))
    print(f"Wrote {out} ({len(data['managed_files'])} managed files)")
