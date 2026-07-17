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


class NoCacheStaticFiles(StaticFiles):
    """Serve desktop UI assets without browser cache stickiness."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    # Startup
    settings.ensure_directories()

    # ── Auto-migrate execution_events to NIS2/SOC2 schema ──────
    try:
        from shogun.db.engine import async_session_factory, engine
        from sqlalchemy import text, inspect as sa_inspect
        async with engine.begin() as conn:
            # Keep desktop installs compatible when they predate Alembic's Flow
            # Stacking revisions. SQLite's create_all cannot add columns to an
            # existing table, so add only the missing, backward-compatible fields.
            table_names = await conn.run_sync(lambda c: sa_inspect(c).get_table_names())
            if "agent_flows" in table_names:
                flow_columns = set(await conn.run_sync(
                    lambda c: [col["name"] for col in sa_inspect(c).get_columns("agent_flows")]
                ))
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
                }
                for column, definition in flow_additions.items():
                    if column not in flow_columns:
                        await conn.execute(text(f"ALTER TABLE agent_flows ADD COLUMN {column} {definition}"))
            if "agent_flow_runs" in table_names:
                run_columns = set(await conn.run_sync(
                    lambda c: [col["name"] for col in sa_inspect(c).get_columns("agent_flow_runs")]
                ))
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
            columns = await conn.run_sync(
                lambda c: [col["name"] for col in sa_inspect(c).get_columns("execution_events")]
                if "execution_events" in sa_inspect(c).get_table_names() else []
            )
            if columns and ("event_category" not in columns or "confidence_score" not in columns):
                # Schema missing NIS2/SOC2 or EU AI Act columns — rebuild
                await conn.execute(text("DROP TABLE IF EXISTS execution_events"))
                import logging
                logging.getLogger(__name__).info("Migrated execution_events schema (NIS2/SOC2 + EU AI Act)")
            # Ensure table exists with full schema
            from shogun.db.base import Base
            import shogun.db.models  # noqa: F401
            await conn.run_sync(Base.metadata.create_all)
        from shogun.services.model_router import ModelRoutingService
        async with async_session_factory() as session:
            routing = ModelRoutingService(session)
            await routing.ensure_defaults()
            await routing.registry.sync_connected()
            await session.commit()
        from shogun.services.stack_orchestrator import recover_interrupted_stack_runs
        await recover_interrupted_stack_runs()
    except Exception:
        pass  # Non-fatal — table will be created on first use

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

    # ── Auto-migrate skill_installations: add openclaw_skill_id ───
    try:
        from shogun.db.engine import engine
        from sqlalchemy import text, inspect as sa_inspect
        async with engine.begin() as conn:
            columns = await conn.run_sync(
                lambda c: [col["name"] for col in sa_inspect(c).get_columns("skill_installations")]
                if "skill_installations" in sa_inspect(c).get_table_names() else []
            )
            if columns and "openclaw_skill_id" not in columns:
                await conn.execute(text(
                    "ALTER TABLE skill_installations ADD COLUMN openclaw_skill_id VARCHAR(255)"
                ))
                import logging
                logging.getLogger(__name__).info("Migrated skill_installations: added openclaw_skill_id column")
    except Exception:
        pass  # Non-fatal

    # ── Backfill openclaw_skill_id from skill.manifest for existing rows ──
    try:
        from shogun.db.engine import async_session_factory
        from shogun.db.models.skill_installation import SkillInstallation
        from shogun.db.models.skill import Skill
        from sqlalchemy import select
        from sqlalchemy.orm import joinedload
        async with async_session_factory() as session:
            result = await session.execute(
                select(SkillInstallation)
                .where(SkillInstallation.openclaw_skill_id.is_(None))
                .options(joinedload(SkillInstallation.skill))
            )
            installations = list(result.scalars().all())
            patched = 0
            for inst in installations:
                if inst.skill and inst.skill.manifest:
                    oc_id = inst.skill.manifest.get("openclaw_id")
                    if oc_id:
                        inst.openclaw_skill_id = oc_id
                        patched += 1
            if patched:
                await session.commit()
                import logging
                logging.getLogger(__name__).info(
                    f"Backfilled openclaw_skill_id for {patched} existing installation(s)"
                )
    except Exception:
        pass  # Non-fatal

    # Ensure built-in OpenClaw Dojo MCP connector exists for agent tools
    try:
        import uuid
        from sqlalchemy import select
        from shogun.db.engine import async_session_factory
        from shogun.db.models.tool_connector import ToolConnector

        async with async_session_factory() as session:
            result = await session.execute(
                select(ToolConnector).where(ToolConnector.slug == "openclaw-dojo")
            )
            if not result.scalars().first():
                session.add(ToolConnector(
                    id=uuid.uuid4(),
                    name="OpenClaw Dojo",
                    slug="openclaw-dojo",
                    connector_type="mcp",
                    source="builtin",
                    status="connected",
                    auth_type="custom",
                    scope="dojo openclaw skills badges achievements transcript",
                    risk_level="medium",
                    config={
                        "command": "shogun-python",
                        "args": ["-m", "shogun.mcp.openclaw_dojo"],
                        "env": {},
                        "transport": "stdio",
                        "builtin": True,
                    },
                    health_status="unknown",
                    created_by="startup",
                    updated_by="startup",
                ))
                await session.commit()
    except Exception:
        pass  # Non-fatal

    # Ensure bushido_schedules table exists and presets are seeded
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

    # ── Start backup scheduler if enabled
    try:
        from shogun.services.backup_scheduler import sync_backup_schedule
        await sync_backup_schedule()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Backup scheduler startup failed: %s", exc)

    # ── Start Telegram Autonomous Poller
    telegram_task = None
    try:
        from shogun.services.telegram_poller import telegram_poller_task
        import asyncio
        telegram_task = asyncio.create_task(telegram_poller_task())
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("Telegram poller startup failed: %s", exc)

    # ── EVENT: System Startup ─────────────────────────────────
    try:
        from shogun.services.event_logger import EventLogger
        import platform
        await EventLogger.emit_system_event(
            "system.startup", "Shogun server started",
            detail={
                "version": "1.3.2",
                "platform": platform.system(),
                "python": platform.python_version(),
            },
        )
    except Exception:
        pass

    # ── Office App Mode: Detection + temp cleanup ─────────────
    import asyncio as _aio
    try:
        from shogun.office.office_detector import detect_office_applications
        from shogun.office.config import load_office_config
        from shogun.office.output_versioning import cleanup_temp_folder
        import logging as _log

        # Run synchronous Office detection in a thread with a hard timeout
        # to prevent COM hangs (e.g. Outlook profile dialogs) from blocking startup
        loop = _aio.get_running_loop()
        office_detection = await _aio.wait_for(
            loop.run_in_executor(None, detect_office_applications),
            timeout=10.0,
        )
        _log.getLogger(__name__).info("Office detection: %s", office_detection.message)
        # Run temp cleanup on startup if configured
        office_cfg = load_office_config()
        if office_cfg.temp_cleanup_on_startup and office_cfg.folders.temp:
            cleaned = cleanup_temp_folder(office_cfg.folders.temp)
            if cleaned:
                _log.getLogger(__name__).info("Office temp cleanup: removed %d files", cleaned)
    except (TimeoutError, _aio.TimeoutError):
        import logging
        logging.getLogger(__name__).warning("Office detection timed out after 10s — skipping")
    except Exception as exc:
        import logging
        logging.getLogger(__name__).debug("Office detection/cleanup skipped: %s", exc)

    # ── Start Gensui Membership Client ────────────────────────
    gensui = None
    if settings.gensui_enabled:
        try:
            from shogun.services.gensui_client import gensui_client
            gensui = gensui_client
            await gensui.start()
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Gensui client startup failed: %s", exc)

    yield

    # Shutdown
    # Close all active Mado browser sessions
    try:
        from shogun.services.mado_service import close_all_browsers
        closed = await close_all_browsers()
        if closed:
            import logging
            logging.getLogger(__name__).info("Mado: closed %d browser sessions on shutdown", closed)
    except Exception:
        pass

    # Stop Ronin and Komainu
    try:
        from shogun.ronin.core.komainu import stop_komainu
        stop_komainu()
        from shogun.db.engine import async_session_factory
        from shogun.db.models.ronin_session import RoninSession
        from sqlalchemy import update
        async with async_session_factory() as session:
            await session.execute(
                update(RoninSession)
                .where(RoninSession.status.in_(["active", "paused", "idle"]))
                .values(status="closed")
            )
            await session.commit()
    except Exception:
        pass

    # Close all Office COM instances
    try:
        from shogun.office.process_manager import get_process_manager
        from shogun.office.com_thread_pool import run_com, shutdown_pool
        pm = get_process_manager()
        closed = pm.close_all()
        if closed:
            import logging
            logging.getLogger(__name__).info("Office: closed %d COM instances on shutdown", closed)
        shutdown_pool()
    except Exception:
        pass

    try:
        from shogun.services.event_logger import EventLogger as _EL
        import asyncio
        await _EL.emit_system_event("system.shutdown", "Shogun server shutting down")
    except Exception:
        pass
    if telegram_task:
        telegram_task.cancel()
    try:
        from shogun.scheduler import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass

    # ── Stop Gensui client ───────────────────────────────────
    if gensui:
        try:
            await gensui.stop()
        except Exception:
            pass

    from shogun.db.engine import engine
    await engine.dispose()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Shogun",
        description="AI Agent Framework — REST API",
        version="1.11.0",
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
    from shogun.api.updates import router as updates_router
    from shogun.api.backups import router as backups_router
    from shogun.api.email import router as email_router
    from shogun.api.calendar import router as calendar_router
    from shogun.api.comms import router as comms_router
    from shogun.api.visual import router as visual_router
    from shogun.api.agent_flow import router as agent_flow_router
    from shogun.api.stack_orchestrator import router as stack_orchestrator_router
    from shogun.api.mado import router as mado_router
    from shogun.api.gensui_config import router as gensui_config_router
    from shogun.api.ronin import router as ronin_router
    from shogun.nexus.gateway.external_gateway import router as nexus_router
    from shogun.api.teams import command_router as katana_command_router, router as teams_router
    from shogun.api.ide import router as ide_router

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
    app.include_router(updates_router, prefix=prefix)
    app.include_router(backups_router, prefix=prefix)
    app.include_router(email_router, prefix=prefix)
    app.include_router(calendar_router, prefix=prefix)
    app.include_router(comms_router, prefix=prefix)
    app.include_router(visual_router, prefix=prefix)
    app.include_router(agent_flow_router, prefix=prefix)
    app.include_router(stack_orchestrator_router, prefix=prefix)
    app.include_router(mado_router, prefix=prefix)
    app.include_router(gensui_config_router, prefix=prefix)
    app.include_router(ronin_router, prefix=prefix)
    app.include_router(teams_router, prefix=prefix)
    app.include_router(katana_command_router, prefix=prefix)
    app.include_router(ide_router, prefix=prefix)

    # Office App Mode (Katana)
    from shogun.api.office import router as office_router
    app.include_router(office_router, prefix=prefix)

    # Workspace File Explorer
    from shogun.api.workspace import router as workspace_router
    app.include_router(workspace_router, prefix=prefix)

    app.include_router(nexus_router, prefix=prefix)

    # ── Health / Identity Endpoint ───────────────────────────
    # Used by Gensui network scanner to identify Shogun instances on the LAN.
    @app.get("/api/v1/health")
    async def health_check():
        import json
        version_file = PROJECT_ROOT / "version.json"
        version_info = {}
        if version_file.exists():
            version_info = json.loads(version_file.read_text(encoding="utf-8"))

        shogun_id = None
        try:
            from shogun.config import settings as _s
            shogun_id = getattr(_s, "shogun_id", None)
        except Exception:
            pass

        return {
            "service": "shogun",
            "status": "ok",
            "version": version_info.get("version", "unknown"),
            "name": version_info.get("name", "Shogun OS"),
            "build": version_info.get("build"),
            "instance_name": settings.instance_name if hasattr(settings, "instance_name") else None,
            "shogun_id": str(shogun_id) if shogun_id else None,
        }

    # Static serving for user uploads
    uploads_path = Path(settings.uploads_path)
    if uploads_path.exists():
        app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

    # Static serving for Mado screenshots
    mado_screenshots_path = Path(settings.mado_path) / "screenshots"
    if not mado_screenshots_path.exists():
        mado_screenshots_path.mkdir(parents=True, exist_ok=True)
    app.mount("/mado/screenshots", StaticFiles(directory=str(mado_screenshots_path)), name="mado_screenshots")

    # Static serving for Ronin screenshots
    ronin_screenshots_path = Path(settings.ronin_path) / "screenshots"
    if not ronin_screenshots_path.exists():
        ronin_screenshots_path.mkdir(parents=True, exist_ok=True)
    app.mount("/ronin/screenshots", StaticFiles(directory=str(ronin_screenshots_path)), name="ronin_screenshots")

    # Static file serving for React frontend (anchored to PROJECT_ROOT)
    frontend_path = PROJECT_ROOT / "frontend" / "dist"
    if frontend_path.exists():
        app.mount("/assets", NoCacheStaticFiles(directory=str(frontend_path / "assets")), name="static")

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
            response = FileResponse(str(frontend_path / "index.html"))
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response

    return app
