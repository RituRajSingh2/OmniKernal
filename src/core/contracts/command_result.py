"""
CommandResult — Handler Return Contract

The typed return value every command handler must produce.
The Core reads this object to decide what to do next:
  - If .reply is set  → pipe it through adapter.send_message()
  - If .ok is False   → log the failure, trigger ApiWatchdog if API-related

Invariant: Handlers NEVER call send_message() directly.
They return a CommandResult and the Core handles delivery.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

@dataclass
class CommandResult:
    """
    The result of a command handler execution.

    Use the factory class methods to construct instances:
        CommandResult.success(reply="message")
        CommandResult.success(reply=None)   # no reply needed
        CommandResult.error(reason="why")

    Attributes:
        ok:           True if the command executed successfully.
        reply:        Optional reply text. Core calls adapter.send_message() with this.
                      None means no reply is sent.
        error_reason: Human-readable failure reason. Only set when ok=False.
                      Logged by the Core — never sent to the user directly.
    """

    ok: bool
    reply: Optional[str] = None
    error_reason: Optional[str] = None

    @classmethod
    def success(cls, reply: Optional[str] = None) -> "CommandResult":
        """
        Build a successful result.

        Args:
            reply: Optional reply text to send back to the user.
                   If None, the Core skips calling send_message().
        """
        return cls(ok=True, reply=reply)

    @classmethod
    def error(cls, reason: str) -> "CommandResult":
        """
        Build a failure result.

        Args:
            reason: Human-readable description of what went wrong.
                    This is logged — it is NOT sent to the user.
        """
        return cls(ok=False, reply=None, error_reason=reason)

    def __repr__(self) -> str:
        if self.ok:
            return f"CommandResult(ok=True, reply={self.reply!r})"
        return f"CommandResult(ok=False, reason={self.error_reason!r})"
