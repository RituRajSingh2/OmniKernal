import importlib
from typing import TYPE_CHECKING, Any, Optional
from src.core.parser import CommandParser
from src.core.contracts.command_result import CommandResult
from src.core.contracts.command_context import CommandContext

if TYPE_CHECKING:
    from src.database.repository import OmniRepository
    from src.core.contracts.user import User

class EventDispatcher:
    """
    Coordinates the "Process" pipeline.
    DB-backed in Phase 2.
    """

    def __init__(self, repository: "OmniRepository", logger: Any = None):
        self.repository = repository
        self.logger = logger

    async def dispatch(self, sanitized_text: str, user: "User") -> Optional[CommandResult]:
        if not sanitized_text.startswith("!"):
            return None

        parts = sanitized_text.split(" ", 1)
        command_trigger = parts[0][1:].lower()
        
        # 1. Lookup route in DB
        route = await self.repository.get_tool_by_command(command_trigger)
        if not route:
            return None

        # 2. Parse arguments using the pattern from DB
        args = CommandParser.match(sanitized_text, route.pattern)
        if args is None:
            return CommandResult.error(f"Usage: {route.pattern}")

        # 3. Execute handler (Phase 2 uses dynamic import)
        try:
            # Dynamic import of the handler
            # In Phase 1 we had a callback, in Phase 2+ we follow the DESIGN.md lazy load
            module_path, func_name = route.handler_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            handler_func = getattr(module, func_name)
            
            ctx = CommandContext(user=user, logger=self.logger)
            result = await handler_func(args, ctx)
            return result
        except Exception as e:
            if self.logger:
                self.logger.error(f"Dispatcher error executing {command_trigger}: {e}")
            return CommandResult.error(f"Execution failed: {str(e)}")
