"""Enable the repository-managed Git hooks for this clone."""

from __future__ import annotations

import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".githooks"


def main() -> None:
    subprocess.run(
        ["git", "config", "core.hooksPath", ".githooks"],
        cwd=ROOT,
        check=True,
    )
    for hook in HOOKS.iterdir():
        if hook.is_file():
            hook.chmod(
                hook.stat().st_mode
                | stat.S_IXUSR
                | stat.S_IXGRP
                | stat.S_IXOTH
            )
    print("Repository Git hooks enabled.")


if __name__ == "__main__":
    main()
