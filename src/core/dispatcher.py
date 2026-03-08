"""
EventDispatcher — Command Routing & Execution Pipeline

Coordinates the "Process" pipeline:
    sanitized text → route lookup → permission check → parse → execute

BUG 19 fix: Uses CommandRouter for route resolution instead of calling
OmniRepository directly — respects the architectural layering.

BUG 20 fix: Re-checks user role against OMNIKERNAL_ADMINS env var before
permission validation so admin features are actually reachable.

BUG 39 fix: Permission check now uses effective_role (after OMNIKERNAL_ADMINS
elevation) instead of user.role (original frozen field).

BUG 42 fix: Handler import path is prefixed with the plugin root module
(plugins.<plugin_name>.) so importlib resolves handlers correctly for
all plugins, not just echo which happened to be a top-level package.

BUG 53 fix: dispatch() now returns a DispatchResult namedtuple that carries
both the CommandResult AND the resolved tool_id and command_name. This lets
the engine record the correct watchdog failure even when the route was matched
via a regex rule (where the trigger doesn't equal the canonical command name).
"""

import importlib
import os
import inspect # BUG 122
from typing import TYPE_CHECKING, Any, NamedTuple

from src.core.contracts.command_context import CommandContext
from src.core.contracts.command_result import CommandResult
from src.core.parser import CommandParser
from src.core.permissions import PermissionValidator
from src.core.router import CommandRouter  # BUG 19
from src.security.encryption import EncryptionEngine  # BUG 35

if TYPE_CHECKING:
    from src.core.contracts.user import User
    from src.database.repository import OmniRepository


# BUG 53 fix: structured return value carrying route metadata alongside the
# CommandResult. Lets callers (engine) know which tool was actually executed.
class DispatchResult(NamedTuple):
    result: CommandResult | None
    tool_id: int | None        # resolved tool PK (works for regex routes)
    command_name: str | None   # canonical command name (for audit logging)


def _resolve_role(user: "User") -> str:
    """
    BUG 20 fix: Returns the effective role for a user.
    If the user's platform ID appears in OMNIKERNAL_ADMINS, they get 'admin'.
    
    BUG 157 fix: only elevate if current role is objectively weaker than 'admin'.
    
    BUG 261 fix: fetch admins dynamically instead of caching global constant.
    """
    admins = {
        uid.strip()
        for uid in os.getenv("OMNIKERNAL_ADMINS", "").split(",")
        if uid.strip()
    }
    if user.id in admins:
        if not PermissionValidator.check_role(user.role, "admin"):
            return "admin"
    return user.role


class EventDispatcher:
    """
    Coordinates the "Process" pipeline.
    DB-backed in Phase 2. Uses CommandRouter for route resolution (Phase 3).
    """

    def __init__(
        self,
        repository: "OmniRepository",
        logger: Any = None,
        rules_cache: Any | None = None  # BUG 68 (RulesCache)
    ):
        self.repository = repository
        # BUG 19 fix: route resolution goes through CommandRouter
        # BUG 68 fix: pass the shared cache container
        self.router = CommandRouter(repository, cache=rules_cache)
        self.logger = logger

    async def dispatch(self, sanitized_text: str, user: "User") -> DispatchResult | None:
        """
        Dispatches a sanitized command string.

        Returns:
            DispatchResult(result, tool_id, command_name) on a matched route, or
            None if the text doesn't start with '!' or no route is found.

        BUG 53 fix: tool_id is taken directly from the resolved route dict so
        that regex-triggered routes return the correct id to the caller.
        """
        if not sanitized_text.startswith("!"):
            return None

        parts = sanitized_text.split(" ", 1)
        command_trigger = parts[0][1:].lower()

        # 1. Lookup route via CommandRouter (BUG 19 + BUG 30)
        route = await self.router.get_route(command_trigger)
        if not route:
            return None

        # 2. BUG 39 fix: resolve effective role, then check that directly
        effective_role = _resolve_role(user)
        required_role = route.get("required_role", "user") # BUG 71
        if not PermissionValidator.check_role(effective_role, required_role=required_role):
            return DispatchResult(
                result=CommandResult.error(f"Permission denied: {required_role} level required"),
                tool_id=route["id"],
                command_name=route["command_name"],
            )

        # 3. Parse arguments using the pattern from the route
        args = CommandParser.match(sanitized_text, route["pattern"])
        if args is None:
            return DispatchResult(
                result=CommandResult.error(f"Usage: {route['pattern']}"),
                tool_id=route["id"],
                command_name=route["command_name"],
            )

        # 4. Execute handler (lazy import)
        try:
            raw_handler_path = route["handler_path"]  # e.g. "handlers.echo.run"
            plugin_name = route["plugin_name"]         # e.g. "echo"

            # Build absolute dotted path: plugins.echo.handlers.echo
            # BUG 42 fix: prefix handler_path with the plugin's root module
            # BUG 260 fix: ensure handler path doesn't try to escape folder via relative dots
            clean_handler = raw_handler_path.lstrip(".")
            full_handler_path = f"plugins.{plugin_name}.{clean_handler}"
            module_path, func_name = full_handler_path.rsplit(".", 1)

            module = importlib.import_module(module_path)
            handler_func = getattr(module, func_name)

            # BUG 122 fix: ensure handler is a coroutine before awaiting
            if not inspect.iscoroutinefunction(handler_func):
                raise TypeError(
                    f"Handler '{full_handler_path}' is not a coroutine function (use 'async def')."
                )

            # BUG 63: If user was elevated via OMNIKERNAL_ADMINS, we must pass
            # a User object to the context that reflects this role, otherwise
            # handlers calling ctx.user.is_admin() see 'user'.
            context_user = user
            if effective_role != user.role:
                from src.core.contracts.user import User
                context_user = User(
                    id=user.id,
                    display_name=user.display_name,
                    platform=user.platform,
                    role=effective_role
                )

            ctx = CommandContext(
                user=context_user,
                logger=self.logger,
                _repository=self.repository,
                _tool_id=route["id"],
                _decrypter=EncryptionEngine.decrypt,  # BUG 35 fix
            )
            result = await handler_func(args, ctx)
            return DispatchResult(
                result=result,
                tool_id=route["id"],
                command_name=route["command_name"],
            )
        except Exception as e:
            if self.logger:
                self.logger.error(f"Dispatcher error executing {command_trigger}: {e}")
            return DispatchResult(
                result=CommandResult.error(f"Execution failed: {str(e)}"),
                tool_id=route["id"],
                command_name=route["command_name"],
            )
