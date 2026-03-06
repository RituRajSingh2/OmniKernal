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

BUG 35 fix: The EncryptionEngine is now injected as a callable (_decrypter)
at construction time instead of being imported lazily inside get_api_key().
This eliminates the circular import risk, makes the dependency explicit to
static analysers, and allows test code to pass a simple mock decrypter.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

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
        user:       The User who triggered this command.
        logger:     Structured logger scoped to this execution (wired in Phase 1).
        _decrypter: BUG 35 fix — callable (str) -> str provided by the Core.
                    Defaults to EncryptionEngine.decrypt if not injected.
    """

    user: "User"
    logger: Any = field(default=None, repr=False)
    _repository: Optional["OmniRepository"] = field(default=None, repr=False)
    _tool_id: Optional[int] = field(default=None, repr=False)
    # BUG 35 fix: decrypter injected by caller; avoids circular import via lazy hack
    _decrypter: Optional[Callable[[str], str]] = field(default=None, repr=False)

    async def get_api_key(self, service: str) -> str:
        """
        Retrieve and decrypt an API key for the given service.

        BUG 55 fix: The `service` argument was previously accepted but silently
        ignored. It is now used as a human-readable label in error messages and
        debug logging, improving traceability. All API keys are stored per-tool
        (one key per tool_id) — if a future multi-key schema is added, this arg
        will become the lookup key. For now it is a required label that must
        match the service name declared in commands.yaml.

        Args:
            service: Descriptive service name (e.g. 'youtube', 'openai').
                     Used in error messages. Must be non-empty.

        Returns:
            Decrypted plaintext API key — only in handler scope, never logged.

        Raises:
            ValueError: If no API key is configured for this tool.
            RuntimeError: If the context is not fully initialised.
        """
        if not service:
            raise ValueError("get_api_key() requires a non-empty service name.")
        if not self._repository or not self._tool_id:
            raise RuntimeError("Repository or tool_id not configured in CommandContext.")

        encrypted_key = await self._repository.get_api_key(self._tool_id)
        if not encrypted_key:
            raise ValueError(
                f"No API key configured for service '{service}' (tool_id={self._tool_id}). "
                "Register it via OmniRepository.register_tool_requirement()."
            )

        # BUG 35 fix: use injected decrypter if provided (no circular import)
        if self._decrypter is not None:
            return self._decrypter(encrypted_key)

        # Fallback: late import kept as a last resort so callers that haven't
        # been updated to inject _decrypter yet continue to work.
        from src.security.encryption import EncryptionEngine  # noqa: PLC0415
        return EncryptionEngine.decrypt(encrypted_key)

    def __repr__(self) -> str:
        return f"CommandContext(user={self.user!r})"
