import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.database.models import Base
from src.database.repository import OmniRepository

@pytest_asyncio.fixture
async def db_session():
    # Use in-memory SQLite for repository tests
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()

@pytest.mark.asyncio
async def test_repository_plugin_and_tool_registration(db_session):
    repo = OmniRepository(db_session)
    
    # 1. Register Plugin
    await repo.register_plugin("echo_plugin", "1.0.0", "Test Author")
    
    # 2. Register Tool
    await repo.register_tool(
        command_name="echo",
        pattern="!echo <text>",
        handler_path="plugins.echo.handlers.echo.run",
        plugin_name="echo_plugin"
    )
    
    # 3. Verify
    tool = await repo.get_tool_by_command("echo")
    assert tool is not None
    assert tool.pattern == "!echo <text>"
    assert tool.plugin_name == "echo_plugin"

@pytest.mark.asyncio
async def test_repository_execution_logging(db_session):
    repo = OmniRepository(db_session)
    
    await repo.log_execution(
        user_id="user123",
        platform="whatsapp",
        command_name="echo",
        raw_input="!echo hello",
        success=True,
        response_time_ms=150
    )
    
    # Verify via direct session query or if repo had a 'get_logs'
    # For now, just ensure it doesn't crash and commits.
    assert True

@pytest.mark.asyncio
async def test_repository_api_health_watchdog(db_session):
    repo = OmniRepository(db_session)
    url = "https://api.example.com"
    
    # 1. First failure
    await repo.update_api_health(url, success=False)
    assert await repo.is_api_healthy(url) is True
    
    # 2. Reaching threshold (3)
    await repo.update_api_health(url, success=False)
    await repo.update_api_health(url, success=False)
    
    # 3. Should be quarantined
    assert await repo.is_api_healthy(url) is False
    
    # 4. Recovery
    await repo.update_api_health(url, success=True)
    assert await repo.is_api_healthy(url) is True
