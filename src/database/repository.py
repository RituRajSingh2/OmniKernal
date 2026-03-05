"""
Database Repository ΓÇö Encapsulated SQL Logic

Isolates all SQLAlchemy queries. Ensures parameterized inputs and
consistent error handling.
"""

from typing import Optional, Sequence, Any
from datetime import datetime
from sqlalchemy import select, update, insert
from sqlalchemy.ext.asyncio import AsyncSession
from .models import Plugin, Tool, ExecutionLog, ApiHealth

class OmniRepository:
    """
    Main repository for all OmniKernal data access.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    # --- Plugin & Tool Registry ---

    async def register_plugin(self, name: str, version: str, author_name: Optional[str] = None, description: Optional[str] = None):
        """Registers or updates a plugin entry."""
        plugin = Plugin(
            name=name,
            version=version,
            author=author_name,
            description=description
        )
        # Using merge to update if exists
        await self.session.merge(plugin)
        await self.session.commit()

    async def register_tool(self, command_name: str, pattern: str, handler_path: str, plugin_name: str, description: Optional[str] = None):
        """Registers or updates a tool entry."""
        tool = Tool(
            command_name=command_name,
            pattern=pattern,
            handler_path=handler_path,
            plugin_name=plugin_name,
            description=description
        )
        # Check if exists
        existing = await self.get_tool_by_command(command_name)
        if existing:
            existing.pattern = pattern
            existing.handler_path = handler_path
            existing.description = description
        else:
            self.session.add(tool)
        
        await self.session.commit()

    async def get_tool_by_command(self, command_name: str) -> Optional[Tool]:
        """Looks up a tool by its !command trigger."""
        result = await self.session.execute(
            select(Tool).where(Tool.command_name == command_name)
        )
        return result.scalar_one_or_none()

    async def get_all_tools(self) -> Sequence[Tool]:
        """Returns all registered tools."""
        result = await self.session.execute(select(Tool))
        return result.scalars().all()

    # --- Execution Logging ---

    async def log_execution(
        self, 
        user_id: str, 
        platform: str, 
        command_name: str, 
        raw_input: str, 
        success: bool, 
        response_time_ms: Optional[int] = None,
        error_reason: Optional[str] = None
    ):
        """Adds a record to the audit trail."""
        log = ExecutionLog(
            user_id=user_id,
            platform=platform,
            command_name=command_name,
            raw_input=raw_input,
            success=success,
            response_time_ms=response_time_ms,
            error_reason=error_reason
        )
        self.session.add(log)
        await self.session.commit()

    # --- API Health Watchdog ---

    async def update_api_health(self, url: str, success: bool):
        """Updates failure counts and quarantine status for an API."""
        health = await self.session.get(ApiHealth, url)
        
        if not health:
            health = ApiHealth(url=url)
            self.session.add(health)

        if success:
            health.consecutive_failures = 0
            health.last_success = datetime.utcnow()
            health.is_quarantined = False
        else:
            health.consecutive_failures += 1
            health.last_failure = datetime.utcnow()
            if health.consecutive_failures >= health.error_threshold:
                health.is_quarantined = True
        
        await self.session.commit()

    async def is_api_healthy(self, url: str) -> bool:
        """Returns False if the API is quarantined."""
        health = await self.session.get(ApiHealth, url)
        if health:
            return not health.is_quarantined
        return True
