"""FastAPI application factory — Bare-bones Shogun AgentFlow edition."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from shogun import __version__
from shogun.config import settings
from shogun.services.oauth_callback_relay import OAuthCallbackLogFilter

logging.getLogger("uvicorn.access").addFilter(OAuthCallbackLogFilter())

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class NoCacheStaticFiles(StaticFiles):
    """Serve desktop UI assets without browser cache stickiness."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


async def _initialize_database() -> None:
    """Ensure core AgentFlow, AI Provider, and Model Routing tables and columns exist."""
    from sqlalchemy import inspect as sa_inspect
    from sqlalchemy import text

    import shogun.db.models  # noqa: F401
    from shogun.db.base import Base
    from shogun.db.engine import async_session_factory, engine
    from shogun.services.model_router import ModelRoutingService
    from shogun.services.provider_credentials import migrate_provider_credentials

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        table_names = await conn.run_sync(lambda c: sa_inspect(c).get_table_names())
        if "agent_flows" in table_names:
            flow_columns = set(
                await conn.run_sync(
                    lambda c: [col["name"] for col in sa_inspect(c).get_columns("agent_flows")]
                )
            )
            flow_additions = {
                "version": "INTEGER NOT NULL DEFAULT 1",
                "flow_type": "VARCHAR(50) NOT NULL DEFAULT 'standard'",
                "input_contract": "TEXT NOT NULL DEFAULT '{}'",
                "output_contract": "TEXT NOT NULL DEFAULT '{}'",
                "risk_tier": "VARCHAR(20) NOT NULL DEFAULT 'low'",
                "default_timeout_seconds": "INTEGER NOT NULL DEFAULT 600",
                "allow_as_subflow": "BOOLEAN NOT NULL DEFAULT 1",
                "required_tools": "TEXT NOT NULL DEFAULT '[]'",
                "is_template": "BOOLEAN NOT NULL DEFAULT 0",
                "template_category": "VARCHAR(100)",
                "template_source": "VARCHAR(30)",
                "template_config": "TEXT NOT NULL DEFAULT '{}'",
                "seed": "INTEGER",
                "seed_model_id": "VARCHAR(600)",
            }
            for column, definition in flow_additions.items():
                if column not in flow_columns:
                    await conn.execute(text(f"ALTER TABLE agent_flows ADD COLUMN {column} {definition}"))
        if "agent_flow_runs" in table_names:
            run_columns = set(
                await conn.run_sync(
                    lambda c: [col["name"] for col in sa_inspect(c).get_columns("agent_flow_runs")]
                )
            )
            run_additions = {
                "flow_version": "INTEGER NOT NULL DEFAULT 1",
                "root_run_id": "VARCHAR(36) NOT NULL DEFAULT ''",
                "parent_run_id": "VARCHAR(36)",
                "parent_node_id": "VARCHAR(36)",
                "run_depth": "INTEGER NOT NULL DEFAULT 0",
                "input_payload": "TEXT NOT NULL DEFAULT '{}'",
                "output_payload": "TEXT NOT NULL DEFAULT '{}'",
                "artifacts": "TEXT NOT NULL DEFAULT '[]'",
                "governance_context": "TEXT NOT NULL DEFAULT '{}'",
            }
            for column, definition in run_additions.items():
                if column not in run_columns:
                    await conn.execute(text(f"ALTER TABLE agent_flow_runs ADD COLUMN {column} {definition}"))
            if "root_run_id" not in run_columns:
                await conn.execute(text("UPDATE agent_flow_runs SET root_run_id = id WHERE root_run_id = ''"))

    async with async_session_factory() as session:
        await migrate_provider_credentials(session)
        routing = ModelRoutingService(session)
        await routing.ensure_defaults()
        await routing.registry.sync_connected()
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    settings.validate_security()
    settings.ensure_directories()

    await _initialize_database()

    try:
        from shogun.db.engine import async_session_factory
        from shogun.scheduler import start_scheduler, sync_flow_schedules

        await start_scheduler()
        async with async_session_factory() as session:
            await sync_flow_schedules(session)
            await session.commit()
    except Exception as exc:
        logging.getLogger(__name__).warning("AgentFlow scheduler startup failed: %s", exc)

    yield

    try:
        from shogun.engine.flow_engine import cancel_all_flow_runs

        await cancel_all_flow_runs("Server shutting down")
    except Exception:
        pass

    try:
        from shogun.services.codex_app_server import shutdown_codex_app_server

        await shutdown_codex_app_server()
    except Exception:
        pass

    try:
        from shogun.scheduler import stop_scheduler

        await stop_scheduler()
    except Exception:
        pass

    from shogun.db.engine import engine

    await engine.dispose()


def create_app() -> FastAPI:
    """Build and configure the bare-bones AgentFlow FastAPI application."""
    app = FastAPI(
        title="Shogun AgentFlow",
        description="Minimal AgentFlow Workflow Engine & Control Plane",
        version=__version__,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    from shogun.api.control_plane_auth import (
        add_security_headers,
        enforce_control_plane_access,
        enforce_rate_limit,
    )

    app.middleware("http")(enforce_control_plane_access)
    app.middleware("http")(enforce_rate_limit)
    app.middleware("http")(add_security_headers)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_origin_regex=r"^https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d+)?$",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from shogun.api.agent_flow import router as agent_flow_router
    from shogun.api.mapping_rpa import router as mapping_rpa_router
    from shogun.api.model_providers import router as models_router
    from shogun.api.stack_orchestrator import router as stack_orchestrator_router
    from shogun.api.system import router as system_router
    from shogun.api.transformation_profiles import router as transformation_profiles_router
    from shogun.api.workspace import router as workspace_router

    prefix = "/api/v1"
    app.include_router(system_router, prefix=prefix)
    app.include_router(models_router, prefix=prefix)
    app.include_router(agent_flow_router, prefix=prefix)
    app.include_router(mapping_rpa_router, prefix=prefix)
    app.include_router(transformation_profiles_router, prefix=prefix)
    app.include_router(stack_orchestrator_router, prefix=prefix)
    app.include_router(workspace_router, prefix=prefix)

    @app.get("/api/v1/agents")
    async def list_agents_stub():
        """Bare-bones edition uses inline ad-hoc agents; return empty fleet list."""
        return {"status": "ok", "data": []}

    @app.get("/api/v1/tools")
    async def list_tools_stub():
        """Return available native AgentFlow tools for node inspectors."""
        from shogun.services.native_skills import NATIVE_TOOLS

        return {
            "status": "ok",
            "data": [
                {
                    "name": item["function"]["name"],
                    "description": item["function"].get("description", ""),
                    "source": "native",
                }
                for item in NATIVE_TOOLS
            ],
        }

    @app.get("/api/v1/health")
    async def health_check():
        from shogun.services.release_metadata import get_release_metadata

        version_info = get_release_metadata()
        return {
            "service": "shogun",
            "status": "ok",
            "version": version_info.get("version", __version__),
            "name": "Shogun AgentFlow",
            "build": version_info.get("build"),
            "deployment_mode": settings.deployment_mode,
        }

    uploads_path = Path(settings.uploads_path)
    uploads_path.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

    frontend_path = PROJECT_ROOT / "frontend" / "dist"
    if frontend_path.exists() and (frontend_path / "assets").exists():
        app.mount("/assets", NoCacheStaticFiles(directory=str(frontend_path / "assets")), name="static")

        @app.get("/{full_path:path}")
        async def serve_frontend(full_path: str):
            if full_path.startswith("api/v1") or full_path.startswith("docs") or full_path.startswith("redoc"):
                return None

            frontend_root = os.path.realpath(str(frontend_path))
            candidate = os.path.normpath(os.path.join(frontend_root, full_path.lstrip("/\\")))
            if candidate.startswith(frontend_root + os.sep) and os.path.isfile(candidate):
                return FileResponse(candidate)

            response = FileResponse(str(frontend_path / "index.html"))
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

    return app
