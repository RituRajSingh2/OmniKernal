"""
PlatformAdapter — Abstract Base Class (Hook Contract)

The Core calls ONLY these 4 methods. The user implements them.
The Core never imports any platform SDK (playwright, baileys, etc.) directly.

Invariant: SDK-specific code lives ONLY in adapter_packs/<name>/.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.contracts.message import Message


class PlatformAdapter(ABC):
    """
    Hook contract between the Core and a platform.

    The Core boots by calling connect(), polls via fetch_new_messages(),
    pipes replies through send_message(), and shuts down with disconnect().
    The Core never sees the underlying SDK — only this interface.
    """

    @abstractmethod
    async def connect(self) -> None:
        """
        Start the platform session.

        Open a browser, connect a WebSocket, authenticate via API —
        whatever the platform requires. Core calls this once on boot.
        """
        ...

    @abstractmethod
    async def fetch_new_messages(self) -> list["Message"]:
        """
        Return new unread messages since the last call.

        Read the DOM, poll a socket, hit an endpoint — implementation
        is up to the adapter. Return an empty list if no new messages.
        Never block indefinitely — return promptly each poll cycle.
        """
        ...

    @abstractmethod
    async def send_message(self, to: str, content: str) -> None:
        """
        Send a reply to a user.

        Core calls this when a handler returns CommandResult.reply.
        Implementation types into a chat box, emits to a socket,
        POSTs to an API — whatever the platform requires.

        Args:
            to:      Platform-specific user/chat identifier.
            content: The reply text to send.
        """
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Tear down the session cleanly.

        Close the browser, disconnect the WebSocket, release resources.
        Core calls this on shutdown.
        """
        ...

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """
        Return the platform identifier string.

        Examples: 'whatsapp', 'telegram', 'discord'.
        Used by the Core for logging and adapter registry lookup.
        """
        raise NotImplementedError
