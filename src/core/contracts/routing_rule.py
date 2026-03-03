"""
RoutingRule — Frozen Dataclass Contract

Represents a single command-to-handler mapping, built from a plugin's
commands.yaml. Stored in the DB routing table (Phase 2) and used by
the Core Router to look up handlers for incoming commands.

Invariant: The Core Router reads routing rules from the DB —
it never scans Python files to discover commands.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RoutingRule:
    """
    A single command routing entry.

    Attributes:
        command_name:  The trigger command (e.g. 'echo', 'ytaudio').
        pattern:       Full pattern string (e.g. '!echo <text>').
        handler_path:  Dotted Python path relative to plugin root
                       (e.g. 'handlers.echo.run').
        plugin_name:   Name of the owning plugin (e.g. 'echo').
        requires_api:  If True, Core checks for a valid API key before execution.
    """

    command_name: str
    pattern: str
    handler_path: str
    plugin_name: str
    requires_api: bool = False

    def __repr__(self) -> str:
        return (
            f"RoutingRule(command={self.command_name!r}, "
            f"handler={self.handler_path!r}, plugin={self.plugin_name!r})"
        )
