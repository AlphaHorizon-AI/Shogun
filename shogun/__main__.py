"""Shogun — CLI entry point.

Enables:
    shogun          # starts the server
    python -m shogun  # same thing
"""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path


def _ensure_env_file() -> None:
    """Auto-generate .env from .env.example on first run if missing."""
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        return

    # Try to find .env.example relative to CWD or package root
    candidates = [
        Path(".env.example"),
        Path(__file__).resolve().parent.parent / ".env.example",
    ]
    for example in candidates:
        if example.exists():
            shutil.copy(example, env_path)
            print("[INFO] Created .env from .env.example - edit it to configure API keys.")
            return

    # No example found — write sensible defaults inline
    project_root = Path(__file__).resolve().parent.parent
    env_path.write_text(
        f"APP_ENV=production\n"
        f"DEBUG=false\n"
        f"API_HOST=0.0.0.0\n"
        f"API_PORT=8000\n"
        f"DATABASE_URL=sqlite+aiosqlite:///{project_root}/data/shogun.db\n"
        f"QDRANT_PATH={project_root}/data/qdrant\n"
        f"SECRET_KEY={uuid.uuid4().hex}\n"
        f"VAULT_ENCRYPTION_KEY=change-me-to-a-fernet-base64-key\n"
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


def main() -> None:
    """Start Shogun — Unified FastAPI + React entrypoint."""
    import uvicorn
    import os

    # Step 1: Ensure .env exists
    _ensure_env_file()

    # Step 2: Load config (now that .env is guaranteed)
    from shogun.config import settings
    settings.ensure_directories()

    # Step 3: Auto-bootstrap if needed
    _auto_bootstrap()
    
    # Step 4: Run Server
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
        print(f"  - Serving Shogun at http://{settings.api_host}:{settings.api_port}")
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
    main()
