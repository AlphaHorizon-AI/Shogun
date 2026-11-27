"""Bootstrap script — creates core database tables and seeds default routing profiles."""

from __future__ import annotations

import asyncio

import shogun.db.models  # noqa: F401
from shogun.config import settings
from shogun.db.base import Base
from shogun.db.engine import async_session_factory, engine


async def bootstrap() -> None:
    settings.ensure_directories()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from shogun.services.model_router import ModelRoutingService

    async with async_session_factory() as session:
        routing = ModelRoutingService(session)
        await routing.ensure_defaults()
        await routing.registry.sync_connected()
        await session.commit()

    await engine.dispose()
    print("OK: AgentFlow database and default routing profiles initialized.")


if __name__ == "__main__":
    asyncio.run(bootstrap())
