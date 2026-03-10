"""
WhatsAppPlaywrightAdapter — Scaffold (Phase 4)

This is the structural scaffold for a WhatsApp Web adapter using Playwright.
The Core discovers and validates this pack via adapter.yaml.

Implementation of the actual DOM scraping and WhatsApp Web interaction
is deferred to the user/developer — this file provides the contract skeleton.

Usage:
    1. Install Playwright: pip install playwright && playwright install chromium
    2. Fill in connect(), fetch_new_messages(), send_message(), disconnect()
    3. Run: AdapterLoader.load("whatsapp_playwright")
"""

from src.core.contracts.message import Message
from src.core.contracts.user import User
from src.core.interfaces.platform_adapter import PlatformAdapter

import whatsplay
from whatsplay.object.message import Message as WhatsplayMessage


class WhatsAppPlaywrightAdapter(PlatformAdapter):
    """
    Playwright-based adapter for WhatsApp Web using the whatsplay library.

    Implements the PlatformAdapter hook contract.
    The Core calls connect() -> fetch_new_messages() -> send_message() -> disconnect().
    """

    def __init__(self):
        self._platform_name = "whatsapp"
        # We start the client headful (headless=False) so we can scan the QR code manually for the first time
        self._client = whatsplay.Client(headless=False)
        self._processed_msg_ids = set()

    @property
    def platform_name(self) -> str:
        return self._platform_name

    async def connect(self) -> None:
        """
        Start the Playwright browser and navigate to WhatsApp Web.
        """
        # start() opens WhatsApp Web, and wait_until_logged_in() pauses until the user scans the QR
        await self._client.start()
        await self._client.wait_until_logged_in()

    async def fetch_new_messages(self) -> list[Message]:
        """
        Read unread messages from the WhatsApp Web DOM.
        """
        try:
            # whatsplay reads the unread message dots and extracts the chats
            wp_messages = await self._client.collect_messages()
        except Exception as e:
            print(f"DEBUG: Exception in collect_messages: {e}")
            return []

        parsed_messages = []
        for msg in wp_messages:
            print(f"DEBUG: Found message: text={getattr(msg, 'text', None)}, sender={getattr(msg, 'sender', None)}")
            if not isinstance(msg, WhatsplayMessage):
                continue

            if msg.is_outgoing:
                continue

            # Deduplicate messages by tracking their unique ID
            msg_id = msg.msg_id or str(hash(msg.text + msg.sender + str(msg.timestamp)))
            if msg_id in self._processed_msg_ids:
                continue

            self._processed_msg_ids.add(msg_id)

            user = User(
                id=msg.sender,
                display_name=msg.sender,
                platform=self.platform_name
            )

            parsed = Message(
                id=msg_id,
                raw_text=msg.text,
                user=user,
                timestamp=msg.timestamp,
                platform=self.platform_name
            )
            parsed_messages.append(parsed)

        return parsed_messages

    async def send_message(self, to: str, content: str) -> None:
        """
        Send a reply to a specific chat in WhatsApp Web.
        """
        # to is the exact chat query/name or phone number
        await self._client.send_message(to, content)

    async def disconnect(self) -> None:
        """
        Tear down the Playwright browser session cleanly.
        """
        await self._client.close()
