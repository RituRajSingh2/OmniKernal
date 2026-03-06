"""
src/core/contracts — Typed Data Contracts

Frozen dataclasses and structured objects passed between Core, adapters,
and plugins. These are immutable data shapes — no logic lives here.
"""

from .user import User
from .message import Message
from .plugin_manifest import PluginManifest
from .command_result import CommandResult
from .command_context import CommandContext

__all__ = [
    "User",
    "Message",
    "PluginManifest",
    "CommandResult",
    "CommandContext",
]
