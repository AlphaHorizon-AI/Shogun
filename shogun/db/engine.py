"""Database engine and async session management.

Supports both SQLite (default, zero-install) and PostgreSQL (production).
The driver is auto-detected from DATABASE_URL.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shogun.config import settings

# ── Detect backend ────────────────────────────────────────────
_is_sqlite = settings.database_url.startswith("sqlite")

# ── Engine ────────────────────────────────────────────────────
if _is_sqlite:
    # SQLite: no pool sizing, enable WAL and foreign keys
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # PostgreSQL: full connection pool
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )

# ── Session Factory ───────────────────────────────────────────
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
