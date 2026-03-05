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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .user import User


@dataclass
class CommandContext:
    """
    Safe capability surface provided to command handlers by the Core.

    Attributes:
        user:   The User who triggered this command.
        logger: Structured logger scoped to this execution (wired in Phase 1).
    """

    user: User
    logger: Any = field(default=None, repr=False)
    # get_api_key() will be added as a method in Phase 2.5
    # when EncryptionEngine and repository layer are available.

    async def get_api_key(self, service: str) -> str:
        """
        Retrieve and decrypt an API key for the given service.

        Phase 0 stub — raises NotImplementedError until Phase 2.5
        wires up the EncryptionEngine + ApiKeyRepository.

        Args:
            service: Service name as declared in plugin's commands.yaml
                     (e.g. 'youtube', 'openai').

        Returns:
            Decrypted plaintext API key — only in handler scope, never logged.
        """
        raise NotImplementedError(
            "get_api_key() is not available until Phase 2.5 (Security & Resilience Layer)."
        )

    def __repr__(self) -> str:
        return f"CommandContext(user={self.user!r})"
