from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from shogun import __main__ as shogun_main

ROOT = Path(__file__).resolve().parents[1]


def test_container_mode_skips_env_file_mutation(monkeypatch):
    monkeypatch.setenv("SHOGUN_SKIP_ENV_FILE", "true")
    monkeypatch.setattr(
        shogun_main,
        "_secure_env_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("environment file must not be touched")),
    )

    shogun_main._ensure_env_file()


def test_skip_env_file_also_applies_to_runtime_settings(tmp_path):
    environment = os.environ.copy()
    environment["SHOGUN_SKIP_ENV_FILE"] = "true"
    environment["PYTHONPATH"] = os.pathsep.join(
        path for path in (str(ROOT), environment.get("PYTHONPATH")) if path
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from shogun.config import Settings; "
                "assert Settings.model_config['env_file'] is None"
            ),
        ],
        cwd=tmp_path,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
