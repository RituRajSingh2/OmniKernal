"""
CommandRouter — DB-backed Command Registry

Routes command triggers to their registered handler paths.
Acts as the single point of access for route lookup, keeping
the Dispatcher free of direct DB queries.

BUG 19 fix: CommandRouter is now used by EventDispatcher instead
of the dispatcher calling OmniRepository.get_tool_by_command directly.

BUG 30 fix: get_route() now checks the routing_rules table first for
regex-based overrides before falling back to exact command name lookup.
This implements the DESIGN.md Phase 2 routing strategy.

BUG 45 fix: routing_rules are cached in memory after the first load.
Rules rarely change at runtime; loading them from the DB on every
message (default 1s poll) was a needless DB round-trip per message.
Call invalidate_route_cache() after inserting a new routing rule.
"""

import re
from typing import Any, Optional, Sequence
from src.database.repository import OmniRepository


class RulesCache:
    """
    Mutable container for cached routing rules (BUG 68).
    Allows sharing a cache across multiple ephemeral CommandRouter instances.
    """
    def __init__(self):
        self.rules: Optional[Sequence[Any]] = None


class CommandRouter:
    """
    Registry for all available commands.
    DB-backed in Phase 2+.

    Dispatcher uses this to resolve a command trigger → route dict.

    Resolution order (BUG 30 fix):
      1. Check routing_rules table — first regex pattern that matches wins.
      2. Fall back to exact command name lookup in the tools table.

    BUG 45 fix: routing_rules are loaded once and cached. Call
    invalidate_route_cache() if rules change at runtime.
    """

    def __init__(self, repository: OmniRepository, cache: Optional[RulesCache] = None):
        self.repository = repository
        # BUG 68 fix: use shared cache if provided, else local one
        self._shared_cache = cache
        self._local_cache: Optional[Sequence[Any]] = None

    @property
    def _rules(self) -> Optional[Sequence[Any]]:
        if self._shared_cache:
            return self._shared_cache.rules
        return self._local_cache

    @_rules.setter
    def _rules(self, value: Sequence[Any]):
        if self._shared_cache:
            self._shared_cache.rules = value
        else:
            self._local_cache = value

    def invalidate_route_cache(self) -> None:
        """Clears the cached routing rules."""
        if self._shared_cache:
            self._shared_cache.rules = None
        else:
            self._local_cache = None

    async def get_route(self, command_trigger: str) -> Optional[dict]:
        """
        Looks up a route by command trigger.

        BUG 30 fix: Checks routing_rules (regex overrides) first, then
        falls back to the exact tool command_name lookup.

        BUG 45 fix: routing_rules are cached after first load.

        Args:
            command_trigger: The raw command name without '!' (e.g. 'echo').

        Returns:
            dict with keys: id, command_name, pattern, handler_path, plugin_name
            or None if no route is found.
        """
        # 1. Load rules (cached after first call)
        if self._rules is None:
            self._rules = await self.repository.get_all_routing_rules()

        for rule in self._rules:
            try:
                if re.fullmatch(rule.regex_pattern, command_trigger):
                    # Resolve the tool this rule maps to
                    tool = await self.repository.get_tool_by_id(rule.tool_id)
                    if tool:
                        return {
                            "id": tool.id,
                            "command_name": tool.command_name,
                            "pattern": tool.pattern,
                            "handler_path": tool.handler_path,
                            "plugin_name": tool.plugin_name,
                            "_via_routing_rule": rule.regex_pattern,  # debug aid
                        }
            except re.error:
                # Malformed regex in DB — skip this rule gracefully
                continue

        # 2. Exact command name lookup (fallback)
        tool = await self.repository.get_tool_by_command(command_trigger)
        if not tool:
            return None

        return {
            "id": tool.id,
            "command_name": tool.command_name,
            "pattern": tool.pattern,
            "handler_path": tool.handler_path,
            "plugin_name": tool.plugin_name,
        }

    async def list_commands(self) -> list[str]:
        """Returns all registered commands from the tools table."""
        tools = await self.repository.get_all_tools()
        return [t.command_name for t in tools]
