"""
User — Frozen Dataclass Contract

Represents a platform user who sent a message to the bot.
Constructed by the adapter from raw platform data and passed
through the Core pipeline. Immutable — never modified in flight.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    """
    A user who interacted with the bot on a platform.

    Attributes:
        id:           Platform-specific unique identifier (e.g. phone number, user ID).
        display_name: Human-readable name as seen on the platform.
        platform:     Platform this user belongs to (e.g. 'whatsapp', 'telegram').
        role:         Permission role. Default 'user'. Elevated to 'admin' via config.
    """

    id: str
    display_name: str
    platform: str
    role: str = "user"  # "user" | "admin"

    def is_admin(self) -> bool:
        """Return True if this user has admin role."""
        return self.role == "admin"

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.display_name!r}, platform={self.platform!r}, role={self.role!r})"
