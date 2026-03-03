"""
BaseCommand — Abstract Base Class

Defines the handler contract every command must implement.
Handlers are lazy-imported by the PluginExecutor (Phase 3) —
they are never imported on boot.

Standard handler signature (enforced at execution time):
    async def run(args: dict[str, str], ctx: CommandContext) -> CommandResult
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.contracts.command_context import CommandContext
    from src.core.contracts.command_result import CommandResult


class BaseCommand(ABC):
    """
    Command handler contract.

    Each command in a plugin's commands.yaml maps to a handler module
    that exposes a `run` coroutine. This ABC formalises that contract
    for class-based handlers and tooling. Function-based handlers
    (async def run) are also valid — see commands.yaml spec in DESIGN.md.
    """

    @property
    @abstractmethod
    def command_name(self) -> str:
        """
        The command trigger string without prefix.

        Example: 'echo', 'ytaudio'. Must match the key in commands.yaml.
        """
        ...

    @property
    @abstractmethod
    def pattern(self) -> str:
        """
        The full command pattern including argument placeholders.

        Example: '!echo <text>', '!ytaudio <url>'.
        The Core's Parser uses this for matching and argument extraction.
        """
        ...

    @abstractmethod
    async def run(self, args: dict[str, Any], ctx: "CommandContext") -> "CommandResult":
        """
        Execute the command.

        Args:
            args: Validated, sanitized argument dict from commands.yaml schema.
            ctx:  Safe CommandContext — provides user info, logger, api_key access.

        Returns:
            CommandResult — the Core pipes .reply through adapter.send_message().

        Invariant: Never call send_message() directly from here.
        Return CommandResult.success(reply=...) or CommandResult.error(reason=...).
        """
        ...
