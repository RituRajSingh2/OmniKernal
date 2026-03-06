import importlib
from typing import TYPE_CHECKING, Any, Optional
from src.core.parser import CommandParser
from src.core.permissions import PermissionValidator          # BUG 5: was missing
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

        # 2. BUG 5 fix: enforce permissions before execution
        #    Default required role is "user"; administrators bypass all checks.
        if not PermissionValidator.check_permission(user, required_role="user"):
            return CommandResult.error("Permission denied")

        # 3. Parse arguments using the pattern from DB
        args = CommandParser.match(sanitized_text, route.pattern)
        if args is None:
            return CommandResult.error(f"Usage: {route.pattern}")

        # 4. Execute handler (lazy import — only on first call per command)
        try:
            module_path, func_name = route.handler_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            handler_func = getattr(module, func_name)

            ctx = CommandContext(
                user=user,
                logger=self.logger,
                _repository=self.repository,
                _tool_id=route.id
            )
            result = await handler_func(args, ctx)
            return result
        except Exception as e:
            if self.logger:
                self.logger.error(f"Dispatcher error executing {command_trigger}: {e}")
            return CommandResult.error(f"Execution failed: {str(e)}")
