"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path

from shogun.config import settings

# Calculate project root (assuming this file is in shogun/app.py)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    # Startup
    settings.ensure_directories()

    # ── Auto-heal: promote any stuck 'not_configured' providers to 'connected'
    try:
        from shogun.db.engine import async_session_factory
        from sqlalchemy import text
        async with async_session_factory() as session:
            await session.execute(
                text("UPDATE model_providers SET status = 'connected' WHERE status = 'not_configured'")
            )
            await session.commit()
    except Exception:
        pass  # Non-fatal — don't block startup

    # ── Ensure bushido_schedules table exists and presets are seeded
    try:
        from shogun.services.bushido_engine import ensure_preset_schedules
        await ensure_preset_schedules()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Bushido preset seeding failed: %s", exc)

    # ── Start APScheduler and load all enabled schedules
    try:
        from shogun.scheduler import start_scheduler, sync_all_schedules
        from shogun.db.engine import async_session_factory
        await start_scheduler()
        async with async_session_factory() as session:
            await sync_all_schedules(session)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Bushido scheduler startup failed: %s", exc)

    yield

    # Shutdown
    try:
        from shogun.scheduler import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass

    from shogun.db.engine import engine
    await engine.dispose()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Shogun",
        description="AI Agent Framework — REST API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    from shogun.api.system import router as system_router
    from shogun.api.personas import router as personas_router
    from shogun.api.agents import router as agents_router
    from shogun.api.model_providers import router as models_router
    from shogun.api.tools import router as tools_router
    from shogun.api.security import router as security_router
    from shogun.api.skills import router as skills_router
    from shogun.api.missions import router as missions_router
    from shogun.api.bushido import router as bushido_router
    from shogun.api.channels import router as channels_router
    from shogun.api.logs import router as logs_router
    from shogun.api.memory import router as memory_router
    from shogun.api.dojo import router as dojo_router
    from shogun.api.samurai_roles import router as samurai_roles_router
    from shogun.api.kaizen import router as kaizen_router
    from shogun.api.a2a import a2a_router, workspace_router
    from shogun.api.i18n import router as i18n_router
    from shogun.api.setup import router as setup_router

    prefix = "/api/v1"
    app.include_router(system_router, prefix=prefix)
    app.include_router(personas_router, prefix=prefix)
    app.include_router(agents_router, prefix=prefix)
    app.include_router(models_router, prefix=prefix)
    app.include_router(tools_router, prefix=prefix)
    app.include_router(security_router, prefix=prefix)
    app.include_router(skills_router, prefix=prefix)
    app.include_router(missions_router, prefix=prefix)
    app.include_router(bushido_router, prefix=prefix)
    app.include_router(channels_router, prefix=prefix)
    app.include_router(logs_router, prefix=prefix)
    app.include_router(memory_router, prefix=prefix)
    app.include_router(dojo_router, prefix=prefix)
    app.include_router(samurai_roles_router, prefix=prefix)
    app.include_router(kaizen_router, prefix=prefix)
    app.include_router(a2a_router, prefix=prefix)
    app.include_router(workspace_router, prefix=prefix)
    app.include_router(i18n_router, prefix=prefix)
    app.include_router(setup_router, prefix=prefix)

    # Static serving for user uploads
    uploads_path = Path(settings.uploads_path)
    if uploads_path.exists():
        app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

    # Static file serving for React frontend (anchored to PROJECT_ROOT)
    frontend_path = PROJECT_ROOT / "frontend" / "dist"
    if frontend_path.exists():
        app.mount("/assets", StaticFiles(directory=str(frontend_path / "assets")), name="static")

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            # Avoid intercepting API routes
            if full_path.startswith("api/v1") or full_path.startswith("docs") or full_path.startswith("redoc"):
                return None
            
            # Serve matching files (for icons, extra images outside assets)
            target_file = frontend_path / full_path
            if target_file.is_file():
                return FileResponse(target_file)
            
            # Default to index.html for SPA routing
            return FileResponse(str(frontend_path / "index.html"))

    return app
