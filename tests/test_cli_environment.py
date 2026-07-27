from __future__ import annotations

from shogun import __main__ as shogun_main


def test_container_mode_skips_env_file_mutation(monkeypatch):
    monkeypatch.setenv("SHOGUN_SKIP_ENV_FILE", "true")
    monkeypatch.setattr(
        shogun_main,
        "_secure_env_file",
        lambda _path: (_ for _ in ()).throw(AssertionError("environment file must not be touched")),
    )

    shogun_main._ensure_env_file()
