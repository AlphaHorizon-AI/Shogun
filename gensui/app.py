"""FastAPI application factory for Gensui server."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from gensui.config import gensui_settings

log = logging.getLogger("gensui")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    # ── Startup ──────────────────────────────────────────────
    gensui_settings.validate_security()
    gensui_settings.ensure_directories()
    gensui_settings.validate_security()

    # Create all tables
    import gensui.db.models  # noqa: F401 — register models
    from gensui.db.base import Base
    from gensui.db.engine import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ── Schema migrations (add missing columns to existing tables) ──
    from sqlalchemy import text as sa_text
    async with engine.begin() as conn:
        try:
            await conn.execute(sa_text(
                "ALTER TABLE security_postures ADD COLUMN tool_overrides_json TEXT"
            ))
            log.info("Migration: added tool_overrides_json column to security_postures")
        except Exception:  # noqa: BLE001, S110
            pass  # Column already exists
        try:
            await conn.execute(sa_text(
                "ALTER TABLE security_postures ADD COLUMN advanced_toolgate_json TEXT"
            ))
            log.info("Migration: added advanced_toolgate_json column to security_postures")
        except Exception:  # noqa: BLE001, S110
            pass  # Column already exists
        try:
            await conn.execute(sa_text(
                "ALTER TABLE shogun_members ADD COLUMN member_token_hash VARCHAR(64)"
            ))
            log.info("Migration: added member_token_hash column to shogun_members")
        except Exception:  # noqa: BLE001, S110
            pass  # Column already exists

    # Seed built-in postures and initial admin
    from gensui.db.engine import async_session_factory
    from gensui.services.seed import seed_database

    async with async_session_factory() as session:
        await seed_database(session)

    log.info("Gensui server started on port %d", gensui_settings.gensui_server_port)

    yield

    # ── Shutdown ─────────────────────────────────────────────
    from gensui.db.engine import engine as _engine
    await _engine.dispose()
    log.info("Gensui server shut down")


def create_app() -> FastAPI:
    """Build and configure the Gensui FastAPI application."""
    app = FastAPI(
        title="Gensui",
        description="Central Command & Security Control Plane for Shogun",
        version="0.1.0",
        docs_url="/docs" if gensui_settings.debug else None,
        redoc_url="/redoc" if gensui_settings.debug else None,
        openapi_url="/openapi.json" if gensui_settings.debug else None,
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def capture_request_metadata(request, call_next):
        from gensui.services.request_context import begin_request, end_request

        token = begin_request(request)
        try:
            return await call_next(request)
        finally:
            end_request(token)

    # CORS — allow admin UI connections
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=r"^https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Register API Routers ─────────────────────────────────
    from gensui.api.alerts import router as alerts_router
    from gensui.api.audit import router as audit_router
    from gensui.api.auth import router as auth_router
    from gensui.api.commands import router as commands_router
    from gensui.api.dashboard import router as dashboard_router
    from gensui.api.enrollment import router as enrollment_router
    from gensui.api.fleet_audit import router as fleet_audit_router
    from gensui.api.harakiri import router as harakiri_router
    from gensui.api.heartbeat import router as heartbeat_router
    from gensui.api.identity import router as identity_router
    from gensui.api.members import router as members_router
    from gensui.api.monitoring import router as monitoring_router
    from gensui.api.policy import router as policy_router
    from gensui.api.postures import router as postures_router
    from gensui.api.telemetry import router as telemetry_router

    prefix = "/api/gensui"
    app.include_router(auth_router, prefix=prefix)
    app.include_router(enrollment_router, prefix=prefix)
    app.include_router(heartbeat_router, prefix=prefix)
    app.include_router(telemetry_router, prefix=prefix)
    app.include_router(policy_router, prefix=prefix)
    app.include_router(commands_router, prefix=prefix)
    app.include_router(harakiri_router, prefix=prefix)
    app.include_router(members_router, prefix=prefix)
    app.include_router(postures_router, prefix=prefix)
    app.include_router(audit_router, prefix=prefix)
    app.include_router(alerts_router, prefix=prefix)
    app.include_router(dashboard_router, prefix=prefix)
    app.include_router(monitoring_router, prefix=prefix)
    app.include_router(fleet_audit_router, prefix=prefix)
    app.include_router(identity_router, prefix=prefix)

    # ── Health Check ─────────────────────────────────────────
    @app.get("/api/gensui/health")
    async def health_check():
        return {"status": "ok", "service": "gensui", "version": "0.1.0"}

    # ── Serve Frontend (production) ──────────────────────────
    frontend_dist = gensui_settings.gensui_frontend_dist
    if frontend_dist.exists():
        index_path = frontend_dist / "index.html"

        def serve_spa_index() -> FileResponse:
            # Vite gives bundles content-hashed names. Never cache the SPA shell,
            # otherwise a rebuild can leave the browser requesting a deleted hash.
            return FileResponse(
                str(index_path),
                headers={
                    "Cache-Control": "no-store, no-cache, must-revalidate",
                    "Pragma": "no-cache",
                    "Expires": "0",
                },
            )

        # Serve /assets/* static files
        assets_path = frontend_dist / "assets"
        if assets_path.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_path)), name="static")

        # Explicit root route
        @app.get("/")
        async def serve_root():
            return serve_spa_index()

        # Catch-all for SPA routing — must NOT match /api, /docs, /redoc
        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            if full_path.startswith(("api/", "docs", "redoc", "openapi")):
                raise HTTPException(status_code=404)
            # Serve actual file if it exists (favicon.svg, logo.png, etc.)
            target = frontend_dist / full_path
            if full_path and target.is_file():
                if target == index_path:
                    return serve_spa_index()
                return FileResponse(target)
            # Otherwise serve index.html (SPA client-side routing)
            return serve_spa_index()
    else:
        log.warning(
            "Gensui frontend distribution is missing at %s; UI routes are disabled",
            frontend_dist,
        )

    return app
