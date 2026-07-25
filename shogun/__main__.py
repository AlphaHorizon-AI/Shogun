"""Shogun — CLI entry point.

Enables:
    shogun          # starts the server
    python -m shogun  # same thing
"""

from __future__ import annotations

import secrets
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
            import os

            env = os.environ.copy()
            env["SHOGUN_PROJECT_VENV"] = str(candidate)
            os.execve(
                str(candidate),
                [str(candidate), "-m", "shogun", *sys.argv[1:]],
                env,
            )


def _secure_env_file(env_path: Path) -> None:
    text = env_path.read_text(encoding="utf-8")
    secured = text.replace(
        "SECRET_KEY=change-me-to-a-random-64-char-string",
        f"SECRET_KEY={secrets.token_urlsafe(48)}",
    ).replace(
        "VAULT_ENCRYPTION_KEY=change-me-to-a-fernet-base64-key",
        f"VAULT_ENCRYPTION_KEY={secrets.token_urlsafe(48)}",
    ).replace(
        "SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN=change-me-to-a-random-infrastructure-token",
        f"SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN={secrets.token_urlsafe(48)}",
    )
    if "SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN=\n" in secured:
        secured = secured.replace(
            "SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN=\n",
            f"SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN={secrets.token_urlsafe(48)}\n",
        )
    if secured.rstrip().endswith("SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN="):
        secured = secured.rstrip() + secrets.token_urlsafe(48) + "\n"
    if "SHOGUN_INFRASTRUCTURE_ADMIN_TOKEN=" not in secured:
        secured = secured.rstrip() + (
            f"\nSHOGUN_INFRASTRUCTURE_ADMIN_TOKEN={secrets.token_urlsafe(48)}\n"
        )
    if "DEPLOYMENT_MODE=server" not in secured:
        secured = secured.replace("API_HOST=0.0.0.0", "API_HOST=127.0.0.1")
    if secured != text:
        env_path.write_text(secured, encoding="utf-8")


def _ensure_env_file() -> None:
    """Auto-generate .env from .env.example on first run if missing."""
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        _secure_env_file(env_path)
        return

    # Try to find .env.example relative to CWD or package root
    candidates = [
        Path(".env.example"),
        Path(__file__).resolve().parent.parent / ".env.example",
    ]
    for example in candidates:
        if example.exists():
            shutil.copy(example, env_path)
            _secure_env_file(env_path)
            print("[INFO] Created .env from .env.example - edit it to configure API keys.")
            return

    # No example found — write sensible defaults inline
    project_root = Path(__file__).resolve().parent.parent
    env_path.write_text(
        f"APP_ENV=production\n"
        f"DEBUG=false\n"
        f"API_HOST=127.0.0.1\n"
        f"API_PORT=8000\n"
        f"DATABASE_URL=sqlite+aiosqlite:///{project_root}/data/shogun.db\n"
        f"QDRANT_PATH={project_root}/data/qdrant\n"
        f"SECRET_KEY={secrets.token_urlsafe(48)}\n"
        f"VAULT_ENCRYPTION_KEY={secrets.token_urlsafe(48)}\n"
        f"VAULT_PATH={project_root}/vault\n"
        f"LOG_PATH={project_root}/logs\n"
        f"CONFIG_PATH={project_root}/configs\n",
        encoding="utf-8",
    )
    print(f"[INFO] Created {env_path} with defaults.")


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


def _open_browser_when_ready(url: str, health_url: str, timeout_seconds: int = 180) -> None:
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

    # Step 2: Load config (now that .env is guaranteed)
    from shogun.config import settings

    settings.ensure_directories()

    # Step 3: Auto-bootstrap if needed
    _auto_bootstrap()

    # Step 4: Open browser once the server is actually ready
    url = _browser_url(settings.api_host, settings.api_port)
    if settings.deployment_mode == "desktop" and settings.infrastructure_admin_token:
        from urllib.parse import quote

        url = f"{url}#infrastructure_token={quote(settings.infrastructure_admin_token, safe='')}"
    health_url = f"http://localhost:{settings.api_port}/api/v1/health"
    _open_browser_when_ready(url, health_url)

    # Step 5: Run Server
    print("=" * 60)
    print("  SHOGUN — The Tenshu (FastAPI + React)")
    print("=" * 60)

    if settings.app_env == "development":
        print("  [DEVELOPMENT MODE]")
        print(f"  - Backend: http://{settings.api_host}:{settings.api_port}")
        print("  - Frontend: http://localhost:3000 (run: npm run dev in /frontend)")
        print("-" * 60)

        uvicorn.run(
            "shogun.app:create_app",
            host=settings.api_host,
            port=settings.api_port,
            factory=True,
            reload=True,
            log_level="info",
        )
    else:
        print("  [PRODUCTION MODE]")
        print(f"  - Serving Shogun at {url}")
        print("-" * 60)

        uvicorn.run(
            "shogun.app:create_app",
            host=settings.api_host,
            port=settings.api_port,
            factory=True,
            reload=False,
            log_level="info",
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
