"""
Database Session Management ΓÇö SQLAlchemy Async Engine

Handles initialization of the SQLite/Postgres engine and provides
the async session factory.
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .models import Base

# Default to SQLite for Phase 2
DEFAULT_DB_URL = "sqlite+aiosqlite:///omnikernal.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DB_URL)

# Create async engine
# echo=True logs all generated SQL to the console (useful for Phase 2 debugging)
engine = create_async_engine(DATABASE_URL, echo=True)

# Generate session factory
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def init_db():
    """
    Initializes the database schema.
    In Phase 2, we use Base.metadata.create_all(). 
    In Phase 3+, we will use Alembic migrations.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    """Dependency for obtaining a database session."""
    async with async_session_factory() as session:
        yield session
