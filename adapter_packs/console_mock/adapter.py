"""
ConsoleMockAdapter — In-Memory Testing Adapter

A zero-dependency adapter for smoke tests and CI.
Implements the full PlatformAdapter contract using in-memory queues.
No SDK, no browser, no network — purely synthetic.
"""

from datetime import datetime
from src.core.interfaces.platform_adapter import PlatformAdapter
from src.core.contracts.message import Message
from src.core.contracts.user import User


class ConsoleMockAdapter(PlatformAdapter):
    """
    Mock adapter for testing the Core lifecycle without any platform SDK.

    Pre-load messages into the queue via `inject_message()`,
    then let the Core poll them through `fetch_new_messages()`.
    Sent replies are stored in `sent_messages` for assertion.
    """

    def __init__(self):
        self._platform_name = "console_mock"
        self._message_queue: list[Message] = []
        self.sent_messages: list[str] = []
        self._connected = False

    @property
    def platform_name(self) -> str:
        return self._platform_name

    async def connect(self) -> None:
        self._connected = True
        print("[ConsoleMockAdapter] Connected to virtual console.")

    async def disconnect(self) -> None:
        self._connected = False
        print("[ConsoleMockAdapter] Disconnected.")

    async def fetch_new_messages(self) -> list[Message]:
        if self._message_queue:
            messages = list(self._message_queue)
            self._message_queue.clear()
            return messages
        return []

    async def send_message(self, to: str, content: str) -> None:
        print(f"\n[OUTPUT to {to}] -> {content}\n")
        self.sent_messages.append(content)

    def inject_message(self, raw_text: str, user_id: str = "test_user") -> None:
        """
        Injects a synthetic message into the adapter's queue for testing.

        Args:
            raw_text: The command string (e.g. "!echo hello").
            user_id: The simulated user ID.
        """
        msg = Message(
            id=f"mock_{len(self._message_queue)}",
            raw_text=raw_text,
            user=User(id=user_id, display_name="TestUser", platform="console", role="admin"),
            timestamp=datetime.now(),
            platform="console"
        )
        self._message_queue.append(msg)
