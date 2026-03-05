import pytest
import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.database.models import Base
from src.database.repository import OmniRepository
from src.security.watchdog import ApiWatchdog

@pytest.fixture
async def app_repo():
    """Provides a fresh, in-memory SQLite DB for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        future=True,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    session_factory = async_sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )
    
    async with session_factory() as session:
        yield OmniRepository(session)
        
    await engine.dispose()

@pytest.fixture
def watchdog(app_repo):
    return ApiWatchdog(app_repo)

@pytest.mark.asyncio
async def test_watchdog_quarantine_flow(watchdog, app_repo):
    url = "https://api.github.com"
    tool_id = 99
    
    # Needs 3 failures to quarantine
    assert await watchdog.is_dead(url) is False
    
    await watchdog.record_failure(url, tool_id, "Bad Gateway")
    assert await watchdog.is_dead(url) is False
    
    await watchdog.record_failure(url, tool_id, "Timeout")
    assert await watchdog.is_dead(url) is False
    
    await watchdog.record_failure(url, tool_id, "Connection Refused")
    assert await watchdog.is_dead(url) is True  # Now dead!
    
    # Ensure it logged to DeadApi
    from src.database.models import DeadApi
    from sqlalchemy import select
    result = await app_repo.session.execute(select(DeadApi).where(DeadApi.api_url == url))
    dead_log = result.scalar_one()
    assert dead_log is not None
    assert dead_log.kill_reason == "Connection Refused"
    
    # Test recovery
    await watchdog.record_success(url)
    assert await watchdog.is_dead(url) is False
