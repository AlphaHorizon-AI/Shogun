"""Shogun AgentFlow — CLI entry point."""

from __future__ import annotations

import os
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path


def _reexec_in_project_venv() -> None:
    """Use the project's virtual environment when launched by global Python."""
    project_root = Path(__file__).resolve().parent.parent
    interpreter = Path("Scripts/python.exe") if sys.platform == "win32" else Path("bin/python")
    candidates = [project_root / name / interpreter for name in (".venv", "venv")]
    if any(
        candidate.exists() and Path(sys.prefix).resolve() == candidate.parent.parent.resolve()
        for candidate in candidates
    ):
        return
    for candidate in candidates:
        if candidate.exists():
            env = os.environ.copy()
            env["SHOGUN_PROJECT_VENV"] = str(candidate)
            os.execve(
                str(candidate),
                [str(candidate), "-m", "shogun", *sys.argv[1:]],
                env,
            )
            return


def _ensure_env_file() -> None:
    """Auto-generate .env from .env.example on first run if missing."""
    if os.environ.get("SHOGUN_SKIP_ENV_FILE", "").casefold() in {"1", "true", "yes", "on"}:
        return
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    from shogun.environment_bootstrap import ensure_desktop_environment, secure_environment_file

    if env_path.exists():
        secure_environment_file(env_path)
        return

    cwd_example = Path.cwd() / ".env.example"
    example_path = cwd_example if cwd_example.is_file() else project_root / ".env.example"
    _path, created = ensure_desktop_environment(project_root, example_path=example_path)
    if created:
        print("[INFO] Created a protected local environment file.")


def _auto_bootstrap() -> None:
    """Run bootstrap if the SQLite database does not exist yet."""
    import asyncio

    from shogun.config import settings

    db_url = settings.database_url
    if db_url.startswith("sqlite"):
        db_file = db_url.split("///", 1)[-1] if "///" in db_url else None
        if db_file and not Path(db_file).exists():
            print("[INIT] First run detected - bootstrapping database...")
            from shogun.bootstrap import bootstrap

            asyncio.run(bootstrap())


def _browser_url(host: str, port: int) -> str:
    configured = os.environ.get("SHOGUN_BROWSER_URL")
    if configured:
        return configured
    browser_host = "localhost" if host in {"0.0.0.0", "::"} else host
    return f"http://{browser_host}:{port}/"


def _port_in_use(host: str, port: int) -> bool:
    import socket

    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as listener:
        if sys.platform != "win32":
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind((host, port))
        except OSError:
            return True
    return False


def _existing_shogun_is_ready(health_url: str) -> bool:
    import json
    import urllib.request

    try:
        with urllib.request.urlopen(health_url, timeout=2) as response:
            if response.status != 200:
                return False
            identity = json.load(response)
            return isinstance(identity, dict) and identity.get("service") == "shogun" and identity.get("status") == "ok"
    except Exception:
        return False


def _open_browser_when_ready(
    url: str,
    health_url: str,
    timeout_seconds: int = 120,
    *,
    wait: bool = False,
) -> None:
    import threading
    import time
    import urllib.request
    import webbrowser

    if os.environ.get("SHOGUN_NO_BROWSER", "").lower() in {"1", "true", "yes"}:
        return

    project_root = Path(__file__).resolve().parent.parent

    def open_managed_browser() -> bool:
        if sys.platform != "win32" or os.environ.get("SHOGUN_MANAGED_BROWSER", "").casefold() not in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return False
        import subprocess

        candidates = [
            shutil.which("msedge.exe"),
            shutil.which("chrome.exe"),
            str(Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe"),
            str(Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe"),
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe"),
        ]
        browser = next((Path(item) for item in candidates if item and Path(item).is_file()), None)
        if browser is None:
            return False
        profile = project_root / "data" / "tenshu-browser-profile"
        profile.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(
            [
                str(browser),
                f"--app={url}",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            cwd=str(project_root),
            close_fds=True,
        )
        return True

    def worker() -> None:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(health_url, timeout=2) as response:
                    if 200 <= response.status < 500:
                        break
            except Exception:
                time.sleep(0.35)
        try:
            if open_managed_browser():
                return
            opened = webbrowser.open(url, new=2)
            if not opened and hasattr(os, "startfile"):
                os.startfile(url)  # type: ignore[attr-defined]
        except Exception:
            if hasattr(os, "startfile"):
                try:
                    os.startfile(url)  # type: ignore[attr-defined]
                except Exception:
                    pass

    if wait:
        worker()
    else:
        threading.Thread(target=worker, name="shogun-browser-opener", daemon=True).start()


def _record_startup_failure(exc: BaseException) -> Path:
    project_root = Path(__file__).resolve().parent.parent
    log_path = project_root / "logs" / "startup-error.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        stamp = datetime.now().astimezone().isoformat(timespec="seconds")
        handle.write(f"\n[{stamp}] Shogun startup failed\n")
        if isinstance(exc, SystemExit):
            handle.write(f"Process exited with code {exc.code!r}.\n")
        traceback.print_exception(type(exc), exc, exc.__traceback__, file=handle)
    return log_path


def main() -> None:
    _reexec_in_project_venv()
    import uvicorn

    try:
        from shogun.services.update_installer import prune_legacy_from_manifest

        pruned = prune_legacy_from_manifest(Path(__file__).resolve().parent.parent)
        if pruned:
            print(f"[UPGRADE] Cleaned {pruned} obsolete legacy code files (user files and AgentFlows preserved).")
    except Exception:
        pass

    _ensure_env_file()
    from shogun.config import settings

    settings.ensure_directories()

    url = _browser_url(settings.api_host, settings.api_port)
    health_url = f"http://localhost:{settings.api_port}/api/v1/health"

    if _port_in_use(settings.api_host, settings.api_port):
        if _existing_shogun_is_ready(health_url):
            print(f"[INFO] Shogun is already running on port {settings.api_port}.")
            _open_browser_when_ready(url, health_url, wait=True)
            return
        raise RuntimeError(
            f"Port {settings.api_port} is already in use by another application. "
            "Close that application or configure a different API_PORT before starting Shogun."
        )

    _auto_bootstrap()
    _open_browser_when_ready(url, health_url)

    print("=" * 60)
    print("  SHOGUN — AgentFlow Edition")
    print("=" * 60)
    reload_enabled = settings.app_env == "development" and os.getenv("SHOGUN_DEV_RELOAD", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    uvicorn.run(
        "shogun.app:create_app",
        host=settings.api_host,
        port=settings.api_port,
        factory=True,
        reload=reload_enabled,
        log_level="info",
        timeout_graceful_shutdown=30,
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except BaseException as exc:
        if not isinstance(exc, SystemExit) or exc.code not in (None, 0):
            try:
                failure_log = _record_startup_failure(exc)
                print(f"\n[ERROR] Startup details saved to: {failure_log}", file=sys.stderr)
            except Exception:
                pass
        raise
