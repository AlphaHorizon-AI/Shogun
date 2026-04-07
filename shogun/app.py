"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shogun.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    # Startup
    settings.ensure_directories()
    yield
    # Shutdown
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

    return app
