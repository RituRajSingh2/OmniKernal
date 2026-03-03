"""
Message — Frozen Dataclass Contract

Represents an inbound message returned by adapter.fetch_new_messages().
The Core never constructs this directly — the adapter builds it from
raw platform data (DOM elements, socket payloads, API responses).
Immutable — passed read-only through the entire processing pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .user import User


@dataclass(frozen=True)
class Message:
    """
    An inbound platform message ready for Core processing.

    Attributes:
        id:        Platform-specific message identifier (for dedup / ack).
        raw_text:  The original message text — NOT yet sanitized.
                   The Core passes this through CommandSanitizer before parsing.
        user:      The User who sent this message.
        timestamp: When the message was received (platform time).
        platform:  Which platform this message came from.
    """

    id: str
    raw_text: str
    user: User
    timestamp: datetime
    platform: str

    def __repr__(self) -> str:
        preview = self.raw_text[:40] + "..." if len(self.raw_text) > 40 else self.raw_text
        return f"Message(id={self.id!r}, from={self.user.id!r}, text={preview!r})"
