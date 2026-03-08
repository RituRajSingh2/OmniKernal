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
from collections.abc import Sequence
from typing import Any

from src.database.repository import OmniRepository


class RulesCache:
    """
    Mutable container for cached routing rules (BUG 68).
    Allows sharing a cache across multiple ephemeral CommandRouter instances.
    """
    def __init__(self) -> None:
        self.rules: Sequence[Any] | None = None
        # BUG 170 fix: store regex cache in shared container so it persists across messages
        self.regex_cache: dict[str, re.Pattern] = {}


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

    def __init__(self, repository: OmniRepository, cache: RulesCache | None = None) -> None:
        self.repository = repository
        # BUG 68 fix: use shared cache if provided, else local one
        self._shared_cache = cache
        self._local_cache: Sequence[Any] | None = None
        # BUG 120 + BUG 170 fix: regex cache container (instance-local or shared)
        self._local_regex_cache: dict[str, re.Pattern] = {}

    @property
    def _rules(self) -> Sequence[Any] | None:
        if self._shared_cache:
            return self._shared_cache.rules
        return self._local_cache

    @_rules.setter
    def _rules(self, value: Sequence[Any]) -> None:
        if self._shared_cache:
            self._shared_cache.rules = value
        else:
            self._local_cache = value

    def invalidate_route_cache(self) -> None:
        """Clears the cached routing rules."""
        if self._shared_cache:
            self._shared_cache.rules = None
            self._shared_cache.regex_cache.clear() # BUG 170
        else:
            self._local_cache = None
            self._local_regex_cache.clear()

    def _get_compiled_regex(self, pattern: str) -> re.Pattern:
        """
        BUG 120 + BUG 170 fix: Get pre-compiled regex from the correct cache.
        """
        cache_dict = self._shared_cache.regex_cache if self._shared_cache else self._local_regex_cache
        if pattern not in cache_dict:
            cache_dict[pattern] = re.compile(pattern)
        return cache_dict[pattern]

    async def get_route(self, command_trigger: str) -> dict[str, Any] | None:
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

        rules = self._rules or []
        for rule in rules:
            try:
                # BUG 120 fix: use pre-compiled regex from cache
                pattern_obj = self._get_compiled_regex(rule.regex_pattern)
                
                if pattern_obj.fullmatch(command_trigger):
                    # Resolve the tool this rule maps to (BUG 70: pre-fetched)
                    tool = rule.tool
                    if tool:
                        return {
                            "id": tool.id,
                            "command_name": tool.command_name,
                            "pattern": tool.pattern,
                            "handler_path": tool.handler_path,
                            "plugin_name": tool.plugin_name,
                            "required_role": tool.required_role,  # BUG 71
                            "_via_routing_rule": rule.regex_pattern,  # debug aid
                        }
            except re.error:
                # Malformed regex in DB — skip this rule gracefully
                continue

        # 2. Exact command name lookup (fallback)
        # BUG 30 + BUG 271 fix: exact match using normalized trigger
        # We lower() it here to handle cases where dispatcher didn't, or DB changed.
        tool = await self.repository.get_tool_by_command(command_trigger.lower())
        if not tool:
            return None

        return {
            "id": tool.id,
            "command_name": tool.command_name,
            "pattern": tool.pattern,
            "handler_path": tool.handler_path,
            "plugin_name": tool.plugin_name,
            "required_role": tool.required_role, # BUG 71
        }

    async def list_commands(self) -> list[str]:
        """Returns all registered commands from the tools table."""
        tools = await self.repository.get_all_tools()
        return [t.command_name for t in tools]
