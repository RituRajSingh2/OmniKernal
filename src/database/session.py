"""
Database Session Management — SQLAlchemy Async Engine

Handles initialization of the SQLite/Postgres engine and provides
the async session factory.

BUG 9 note: The engine and session_factory are created as module-level globals,
which means any import of this module triggers DB engine creation. For test
isolation, set the DATABASE_URL environment variable to an in-memory URL BEFORE
importing this module:
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
Tests that need full isolation (e.g. test_watchdog.py) create their own engine
independently, which is the recommended pattern for unit tests.
"""

import os
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .models import Base

# Default to SQLite for Phase 2; override via DATABASE_URL env var for Postgres/MySQL
DEFAULT_DB_URL = "sqlite+aiosqlite:///omnikernal.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# BUG 9 fix: removed echo=True — it was logging every SQL statement to stdout,
# which pollutes test output and is not appropriate outside of debugging sessions.
# Set SQLALCHEMY_ECHO=1 env var if you need SQL tracing temporarily.
_echo = os.getenv("SQLALCHEMY_ECHO", "").lower() in ("1", "true", "yes")

engine = create_async_engine(DATABASE_URL, echo=_echo)

async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

_db_initialized: bool = False


async def init_db() -> None:
    """
    Initializes the database schema.
    In Phase 2, we use Base.metadata.create_all().
    In Phase 3+, we will use Alembic migrations.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_db_initialized() -> None:
    """
    BUG 36 fix: Idempotent DB initialization guard.

    Safe to call from any entry point (CLI scripts, test helpers, adapters)
    that uses OmniRepository without going through OmniKernal.start().
    On the first call it runs Base.metadata.create_all(); subsequent calls
    are no-ops (guarded by module-level flag).

    Usage::

        from src.database.session import ensure_db_initialized
        await ensure_db_initialized()
        async with async_session_factory() as session:
            repo = OmniRepository(session)
    """
    global _db_initialized
    if not _db_initialized:
        await init_db()
        _db_initialized = True

async def get_db() -> AsyncIterator[AsyncSession]:
    """Dependency for obtaining a database session."""
    async with async_session_factory() as session:
        yield session


async def dispose_db() -> None:
    """
    BUG 116 fix: Cleanly disposes the database engine.
    Should be called during service shutdown to close pools.
    """
    await engine.dispose()
