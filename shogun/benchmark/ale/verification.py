"""Visible-instruction verification for ALE benchmark outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import ALETask


class ALEInstructionVerifier:
    @staticmethod
    def verify(task: ALETask, exported_files: list[Path]) -> dict[str, Any]:
        checks: list[dict[str, str]] = []
        by_name = {path.name.lower(): path for path in exported_files if path.exists()}
        for expected in task.expected_outputs:
            name = Path(expected).name.lower()
            found = by_name.get(name)
            checks.append(
                {
                    "name": f"required_file_exists:{name}",
                    "status": "passed" if found and found.stat().st_size > 0 else "failed",
                    "evidence": str(found) if found else "missing",
                }
            )
        if not checks:
            nonempty = [path for path in exported_files if path.exists() and path.stat().st_size > 0]
            checks.append(
                {
                    "name": "nonempty_artifact_created",
                    "status": "passed" if nonempty else "failed",
                    "evidence": str(nonempty[0]) if nonempty else "no exported file",
                }
            )
        passed = all(item["status"] == "passed" for item in checks)
        return {"status": "passed" if passed else "failed", "checks": checks, "retry_recommended": not passed}
