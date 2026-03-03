from typing import Any, Optional
from src.database.repository import OmniRepository

class CommandRouter:
    """
    Registry for all available commands. 
    DB-backed in Phase 2.
    """
    
    def __init__(self, repository: OmniRepository):
        self.repository = repository

    async def get_route(self, command_name: str):
        """Looks up a route by command name from the database."""
        tool = await self.repository.get_tool_by_command(command_name)
        if not tool:
            return None
            
        # Transform DB model to a simple dict for the dispatcher
        return {
            "command_name": tool.command_name,
            "pattern": tool.pattern,
            "handler_path": tool.handler_path,
            "plugin_name": tool.plugin_name
        }

    async def list_commands(self) -> list[str]:
        """Returns all registered commands from DB."""
        tools = await self.repository.get_all_tools()
        return [t.command_name for t in tools]
