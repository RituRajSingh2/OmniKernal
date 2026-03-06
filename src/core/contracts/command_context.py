"""
CommandContext — Safe Capability Surface for Handlers

The controlled object the Core passes to every handler at execution time.
Handlers receive ONLY what they need — nothing more. This is the
single point of access for DB-backed capabilities (API key decryption,
structured logging).

Phase 0: Stub with user + logger fields.
Phase 1: logger wired to Core's Loguru logger.
Phase 2.5: get_api_key() wired to EncryptionEngine + repository.
Phase 3: Full context passed into every handler execution.

Invariant: Handlers access the DB ONLY through ctx.get_api_key().
No raw DB session is ever exposed to handler scope.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from .user import User
    from src.database.repository import OmniRepository


# BUG 14: frozen=True prevents handlers from mutating ctx.user / ctx.logger
# after construction. get_api_key() only reads fields — no conflict with frozen.
@dataclass(frozen=True)
class CommandContext:
    """
    Safe, immutable capability surface provided to command handlers by the Core.

    Attributes:
        user:   The User who triggered this command.
        logger: Structured logger scoped to this execution (wired in Phase 1).
    """

    user: "User"
    logger: Any = field(default=None, repr=False)
    _repository: Optional["OmniRepository"] = field(default=None, repr=False)
    _tool_id: Optional[int] = field(default=None, repr=False)

    async def get_api_key(self, service: str) -> str:
        """
        Retrieve and decrypt an API key for the given service.

        Args:
            service: Service name as declared in plugin's commands.yaml
                     (e.g. 'youtube', 'openai').

        Returns:
            Decrypted plaintext API key — only in handler scope, never logged.

        Raises:
            ValueError: If no API key is found for this tool or decryption fails.
        """
        if not self._repository or not self._tool_id:
            raise RuntimeError("Repository or tool_id not configured in CommandContext.")

        encrypted_key = await self._repository.get_api_key(self._tool_id)
        if not encrypted_key:
            raise ValueError(
                f"No API key found configured for tool '{service}' (tool_id={self._tool_id})"
            )

        from src.security.encryption import EncryptionEngine
        return EncryptionEngine.decrypt(encrypted_key)

    def __repr__(self) -> str:
        return f"CommandContext(user={self.user!r})"
