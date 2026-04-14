"""Shogun — CLI entry point.

Enables:
    shogun          # starts the server
    python -m shogun  # same thing
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def _ensure_env_file() -> None:
    """Auto-generate .env from .env.example on first run if missing."""
    env_path = Path(".env")
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
            print("📋 Created .env from .env.example — edit it to configure API keys.")
            return

    # No example found — write sensible defaults inline
    env_path.write_text(
        "# Shogun — auto-generated defaults\n"
        "APP_ENV=development\n"
        "DEBUG=true\n"
        "API_HOST=0.0.0.0\n"
        "API_PORT=8000\n"
        "DATABASE_URL=sqlite+aiosqlite:///./data/shogun.db\n"
        "QDRANT_PATH=./data/qdrant\n"
        "SECRET_KEY=change-me-to-a-random-64-char-string\n"
        "VAULT_ENCRYPTION_KEY=change-me-to-a-fernet-base64-key\n"
        "VAULT_PATH=./vault\n"
        "LOG_PATH=./logs\n"
        "CONFIG_PATH=./configs\n",
        encoding="utf-8",
    )
    print("📋 Created .env with defaults — edit it to configure API keys.")


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
            print("🏗  First run detected — bootstrapping database...")
            from shogun.bootstrap import bootstrap
            asyncio.run(bootstrap())
            print()


def main() -> None:
    """Start Shogun — API server and Gradio UI."""
    import gradio as gr
    import uvicorn

    # Step 1: Ensure .env exists
    _ensure_env_file()

    # Step 2: Load config (now that .env is guaranteed)
    from shogun.config import settings

    settings.ensure_directories()

    # Step 3: Auto-bootstrap if needed
    _auto_bootstrap()

    # Step 4: Build app
    from shogun.app import create_app
    from shogun.ui.tenshu import create_tenshu_ui

    api_app = create_app()
    tenshu, theme, css, js = create_tenshu_ui()

    # Gradio 6.0: theme/css/js are passed here, not to gr.Blocks()
    app = gr.mount_gradio_app(
        api_app,
        tenshu,
        path="/",
        theme=theme,
        css=css,
        js=js,
    )

    print("=" * 60)
    print("  SHOGUN — The Tenshu")
    print("=" * 60)
    print(f"  API:  http://localhost:{settings.api_port}/docs")
    print(f"  UI:   http://localhost:{settings.api_port}/")
    print("=" * 60)

    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
