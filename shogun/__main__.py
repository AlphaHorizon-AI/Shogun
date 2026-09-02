"""Shogun — CLI entry point.

Enables:
    shogun          # starts the server
    python -m shogun  # same thing
"""

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
    candidates = [
        project_root / ".venv" / "Scripts" / "python.exe",
        project_root / "venv" / "Scripts" / "python.exe",
        project_root / ".venv" / "bin" / "python",
        project_root / "venv" / "bin" / "python",
    ]
    current = Path(sys.executable).resolve()
    for candidate in candidates:
        if candidate.exists() and candidate.resolve() != current:
            env = os.environ.copy()
            env["SHOGUN_PROJECT_VENV"] = str(candidate)
            os.execve(
                str(candidate),
                [str(candidate), "-m", "shogun", *sys.argv[1:]],
                env,
            )


def _secure_env_file(env_path: Path) -> None:
    from shogun.environment_bootstrap import secure_environment_file

    secure_environment_file(env_path)


def _ensure_env_file() -> None:
    """Auto-generate .env from .env.example on first run if missing."""
    if os.environ.get("SHOGUN_SKIP_ENV_FILE", "").casefold() in {"1", "true", "yes", "on"}:
        # Hardened containers receive all configuration through their runtime
        # environment and deliberately keep the application tree read-only.
        return
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        _secure_env_file(env_path)
        return

    from shogun.environment_bootstrap import ensure_desktop_environment

    cwd_example = Path.cwd() / ".env.example"
    example_path = cwd_example if cwd_example.is_file() else project_root / ".env.example"
    _path, created = ensure_desktop_environment(
        project_root,
        example_path=example_path,
    )
    if created:
        print("[INFO] Created a protected local environment file.")


def _auto_bootstrap() -> None:
    """Run bootstrap if the database does not exist yet."""
    import asyncio

    from shogun.config import settings

    db_url = settings.database_url
    if db_url.startswith("sqlite"):
        # Extract the file path from the SQLite URL
        # Format: sqlite+aiosqlite:///./data/shogun.db
        db_file = db_url.split("///", 1)[-1] if "///" in db_url else None
        if db_file and not Path(db_file).exists():
            print("[INIT] First run detected - bootstrapping database...")
            from shogun.bootstrap import bootstrap

            asyncio.run(bootstrap())
            print()


def _browser_url(host: str, port: int) -> str:
    import os

    configured = os.environ.get("SHOGUN_BROWSER_URL")
    if configured:
        return configured
    browser_host = "localhost" if host in {"0.0.0.0", "::"} else host
    return f"http://{browser_host}:{port}"


def _port_in_use(host: str, port: int) -> bool:
    """Return whether another process already owns the configured listener."""
    import socket

    family = socket.AF_INET6 if ":" in host else socket.AF_INET
    with socket.socket(family, socket.SOCK_STREAM) as listener:
        try:
            listener.bind((host, port))
        except OSError:
            return True
    return False


def _existing_shogun_is_ready(health_url: str) -> bool:
    """Recognize an already-running local Shogun instance."""
    import urllib.request

    try:
        with urllib.request.urlopen(health_url, timeout=2) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def _open_browser_when_ready(
    url: str,
    health_url: str,
    timeout_seconds: int = 180,
    *,
    wait: bool = False,
) -> None:
    """Open the local UI as soon as the server responds."""
    import os
    import threading
    import time
    import urllib.request
    import webbrowser
    from datetime import datetime

    if os.environ.get("SHOGUN_NO_BROWSER", "").lower() in {"1", "true", "yes"}:
        return

    project_root = Path(__file__).resolve().parent.parent
    log_path = project_root / "logs" / "launcher-browser.log"

    def log(message: str) -> None:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"[{stamp}] {message}\n")
        except Exception:
            pass

    def open_managed_browser() -> bool:
        if sys.platform != "win32" or os.environ.get("SHOGUN_MANAGED_BROWSER", "").casefold() not in {
            "1", "true", "yes", "on",
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
        process = subprocess.Popen(
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
        marker = project_root / ".states" / "tenshu-browser.pid"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(process.pid), encoding="ascii")
        log(f"Opened dedicated Tenshu browser process {process.pid} via {browser.name}")
        return True

    def worker() -> None:
        safe_url = url.split("#", 1)[0]
        log(f"Server-side browser opener waiting. Url={safe_url} HealthUrl={health_url}")
        deadline = time.time() + timeout_seconds
        ready = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(health_url, timeout=2) as response:
                    if 200 <= response.status < 500:
                        ready = True
                        log(f"Ready probe succeeded: HTTP {response.status}")
                        break
            except Exception:
                time.sleep(0.35)

        if not ready:
            log("Timed out waiting for readiness; opening URL anyway.")

        try:
            if open_managed_browser():
                return
            opened = webbrowser.open(url, new=2)
            log(f"webbrowser.open returned {opened}")
            if not opened and hasattr(os, "startfile"):
                os.startfile(url)  # type: ignore[attr-defined]
                log("Opened via os.startfile fallback.")
        except Exception as exc:
            log(f"webbrowser.open failed: {exc}")
            if hasattr(os, "startfile"):
                try:
                    os.startfile(url)  # type: ignore[attr-defined]
                    log("Opened via os.startfile fallback after webbrowser error.")
                except Exception as fallback_exc:
                    log(f"os.startfile fallback failed: {fallback_exc}")

    if wait:
        worker()
    else:
        threading.Thread(target=worker, name="shogun-browser-opener", daemon=True).start()


def _record_startup_failure(exc: BaseException) -> Path:
    """Persist launcher failures that would otherwise disappear with the terminal."""
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
    if len(sys.argv) >= 3 and sys.argv[1:3] == ["benchmark", "ale"]:
        from shogun.benchmark.ale.cli import main as benchmark_main

        raise SystemExit(benchmark_main(sys.argv[3:]))

    """Start Shogun — Unified FastAPI + React entrypoint."""

    import uvicorn

    # Step 1: Ensure .env exists
    _ensure_env_file()

    # A Total Restore is applied before importing Settings, opening SQLite, or
    # initializing embedded Qdrant.  This is what makes a clean directory swap
    # possible on Windows and prevents mixed old/new state.
    from shogun.services.complete_backup_service import apply_pending_total_restore

    restore_result = apply_pending_total_restore()
    if restore_result.get("applied"):
        print(
            f"[RESTORE] Restored {restore_result.get('files_restored', 0)} files. "
            f"Safety backup: {restore_result.get('safety_backup')}"
        )
        # The restored .env may contain the original encryption keys and other
        # settings. Re-exec once so Settings is built from that restored file.
        if os.environ.get("SHOGUN_TOTAL_RESTORE_REEXEC") != "1":
            environment = os.environ.copy()
            environment["SHOGUN_TOTAL_RESTORE_REEXEC"] = "1"
            os.execve(sys.executable, [sys.executable, "-m", "shogun", *sys.argv[1:]], environment)

    # Step 2: Load config (now that .env is guaranteed)
    from shogun.config import settings

    settings.ensure_directories()

    # Step 3: Resolve the local endpoints and avoid a second competing server.
    url = _browser_url(settings.api_host, settings.api_port)
    if settings.deployment_mode == "desktop" and settings.infrastructure_admin_token:
        from shogun.environment_bootstrap import build_desktop_browser_url

        url = build_desktop_browser_url(url, settings.infrastructure_admin_token)
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

    # Step 4: Auto-bootstrap if needed
    _auto_bootstrap()

    # Step 5: Open browser once the server is actually ready
    _open_browser_when_ready(url, health_url)

    # Step 6: Run Server
    print("=" * 60)
    print("  SHOGUN — The Tenshu (FastAPI + React)")
    print("=" * 60)

    if settings.app_env == "development":
        development_reload = os.getenv("SHOGUN_DEV_RELOAD", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        print("  [DEVELOPMENT MODE]")
        print(f"  - Backend: http://{settings.api_host}:{settings.api_port}")
        print("  - Frontend: http://localhost:3000 (run: npm run dev in /frontend)")
        print(
            "  - Backend auto-reload: "
            + ("enabled" if development_reload else "disabled (set SHOGUN_DEV_RELOAD=1 to enable)")
        )
        print("-" * 60)

        uvicorn.run(
            "shogun.app:create_app",
            host=settings.api_host,
            port=settings.api_port,
            factory=True,
            reload=development_reload,
            log_level="info",
            timeout_graceful_shutdown=30,
        )
    else:
        print("  [PRODUCTION MODE]")
        print(f"  - Serving Shogun at {url.split('#', 1)[0]}")
        print("-" * 60)

        uvicorn.run(
            "shogun.app:create_app",
            host=settings.api_host,
            port=settings.api_port,
            factory=True,
            reload=False,
            log_level="info",
            timeout_graceful_shutdown=30,
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except BaseException as exc:
        # Uvicorn uses SystemExit for errors such as an occupied port. Record it
        # as well so shortcut launches leave useful evidence behind.
        if not isinstance(exc, SystemExit) or exc.code not in (None, 0):
            try:
                failure_log = _record_startup_failure(exc)
                print(f"\n[ERROR] Startup details saved to: {failure_log}", file=sys.stderr)
            except Exception:
                pass
        raise
