"""Shogun — Main entrypoint.

Runs both the FastAPI backend and Gradio UI.
"""

from __future__ import annotations

import threading
import uvicorn

from shogun.app import create_app
from shogun.config import settings
from shogun.ui.tenshu import create_tenshu_ui


def main():
    """Start Shogun — API server and Gradio UI."""
    import gradio as gr

    settings.ensure_directories()

    # Create FastAPI app
    api_app = create_app()

    # Create Gradio UI
    tenshu = create_tenshu_ui()

    # Mount Gradio onto FastAPI at root
    app = gr.mount_gradio_app(api_app, tenshu, path="/")

    print("=" * 60)
    print("  ⬡ SHOGUN — The Tenshu")
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
