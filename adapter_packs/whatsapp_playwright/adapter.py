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

from src.core.interfaces.platform_adapter import PlatformAdapter
from src.core.contracts.message import Message


class WhatsAppPlaywrightAdapter(PlatformAdapter):
    """
    Playwright-based adapter for WhatsApp Web.

    Implements the PlatformAdapter hook contract.
    The Core calls connect() -> fetch_new_messages() -> send_message() -> disconnect().
    All Playwright/DOM logic lives here — the Core never sees the browser.
    """

    def __init__(self):
        self._platform_name = "whatsapp"
        self._browser = None
        self._page = None
        self._pw = None

    @property
    def platform_name(self) -> str:
        return self._platform_name

    async def connect(self) -> None:
        """
        Start the Playwright browser and navigate to WhatsApp Web.

        TODO (User Implementation):
          1. Launch Chromium via Playwright
          2. Navigate to https://web.whatsapp.com
          3. Wait for QR code scan / session restore
          4. Verify the main chat list is visible
        """
        raise NotImplementedError(
            "WhatsAppPlaywrightAdapter.connect() is a scaffold. "
            "Implement Playwright browser launch and WhatsApp Web auth here."
        )

    async def fetch_new_messages(self) -> list[Message]:
        """
        Read unread messages from the WhatsApp Web DOM.

        TODO (User Implementation):
          1. Query DOM for unread message elements
          2. Parse sender, text, timestamp from each element
          3. Convert to Message objects
          4. Mark messages as read to avoid re-processing
        """
        raise NotImplementedError(
            "WhatsAppPlaywrightAdapter.fetch_new_messages() is a scaffold. "
            "Implement DOM scraping for unread messages here."
        )

    async def send_message(self, to: str, content: str) -> None:
        """
        Send a reply to a specific chat in WhatsApp Web.

        TODO (User Implementation):
          1. Find or open the chat for the 'to' contact
          2. Fill the message input box with 'content'
          3. Press Enter or click Send
        """
        raise NotImplementedError(
            "WhatsAppPlaywrightAdapter.send_message() is a scaffold. "
            "Implement DOM interaction for sending messages here."
        )

    async def disconnect(self) -> None:
        """
        Tear down the Playwright browser session cleanly.

        TODO (User Implementation):
          1. Close browser pages
          2. Close browser instance
          3. Stop Playwright process
        """
        raise NotImplementedError(
            "WhatsAppPlaywrightAdapter.disconnect() is a scaffold. "
            "Implement Playwright teardown here."
        )
