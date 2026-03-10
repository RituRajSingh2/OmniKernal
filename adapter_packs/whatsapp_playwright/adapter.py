"""
WhatsAppPlaywrightAdapter — Phase 4 (whatsplay-backed)

Implements the PlatformAdapter hook contract using the whatsplay library.

Key design decisions:
  - Auth persistence via LocalProfileAuth: saves browser profile to
    profiles/<profile_name>/wa_session/ so QR scan is only needed once.
  - Message polling via _check_unread_chats() + per-chat collect_messages():
    whatsplay's collect_messages() only reads the currently-open chat.
    We must first detect which chats have unread messages, then open
    each one individually to read them.
  - Chat isolation: after reading each unread chat we close it so the
    polling loop doesn't accidentally leave a chat open and interfere
    with the next sweep.
"""

import os
import re
import asyncio
from datetime import datetime, timezone

# WhatsApp Web appends the timestamp directly into the text node that whatsplay
# reads with inner_text(). Strip it before the text reaches the Core.
# Matches: "6:31 PM", "10:30 AM", "7:18 am", "23:45" (24h) at end of string.
_WA_TIMESTAMP_RE = re.compile(
    r"\s*\d{1,2}:\d{2}(?:\s*[APap]\.?[Mm]\.?)?\s*$"
)

from whatsplay import Client
from whatsplay.auth.local_profile_auth import LocalProfileAuth
from whatsplay.object.message import Message as WhatsplayMessage

from src.core.contracts.message import Message
from src.core.contracts.user import User
from src.core.interfaces.platform_adapter import PlatformAdapter


# Directory (relative to CWD) where persistent browser profiles are stored.
# Each adapter instance uses its own sub-directory keyed by profile_name.
_SESSION_BASE_DIR = "profiles"


def _strip_wa_timestamp(text: str) -> str:
    """Remove the trailing WhatsApp timestamp whatsplay concatenates onto msg text."""
    return _WA_TIMESTAMP_RE.sub("", text).strip()


class WhatsAppPlaywrightAdapter(PlatformAdapter):
    """
    Playwright-based adapter for WhatsApp Web using the whatsplay library.

    Implements the PlatformAdapter hook contract:
      connect() -> fetch_new_messages() loop -> send_message() -> disconnect()

    Args:
        profile_name: Used to derive the session persist path.
                      Defaults to "whatsapp_test".
        headless:     Run Chromium headless (requires prior QR scan with headful).
    """

    def __init__(
        self,
        profile_name: str = "whatsapp_test",
        headless: bool = False,
    ) -> None:
        self._platform_name = "whatsapp"
        self._profile_name = profile_name
        self._headless = headless

        # Persistent session directory — saved across runs so QR is only needed once
        session_dir = os.path.join(_SESSION_BASE_DIR, profile_name, "wa_session")
        os.makedirs(session_dir, exist_ok=True)

        self._auth = LocalProfileAuth(data_dir=session_dir, profile="Default")
        self._client = Client(auth=self._auth, headless=headless)

        # Serialise all browser-UI operations (open/close chats, type text).
        # Without this, the poll loop's Escape-press can close a chat that
        # send_message() just opened — causing 'timeout waiting for input box'.
        self._browser_lock: asyncio.Lock = asyncio.Lock()

        # Track message IDs we've already processed to avoid duplicates
        self._processed_msg_ids: set[str] = set()

    # ------------------------------------------------------------------
    # PlatformAdapter ABC
    # ------------------------------------------------------------------

    @property
    def platform_name(self) -> str:
        return self._platform_name

    async def connect(self) -> None:
        """
        Start the Playwright browser, navigate to WhatsApp Web.
        Blocks until the user scans the QR code (or session auto-restores).
        """
        print(f"[WhatsAppAdapter] Starting browser... (session: {self._auth.data_dir})")
        print("[WhatsAppAdapter] If this is the first run, scan the QR code in the browser.")
        print("[WhatsAppAdapter] Subsequent runs will reuse the saved session automatically.\n")

        # start() opens WhatsApp Web and runs the internal whatsplay main loop
        # in the background. We do NOT await it (it blocks indefinitely).
        # Instead we start it as a task and wait until the logged-in state is reached.
        self._start_task = asyncio.create_task(self._client.start())

        # Give the browser time to launch and reach WhatsApp Web
        await asyncio.sleep(3)

        # Wait for login (up to 120s — plenty of time to scan QR)
        print("[WhatsAppAdapter] Waiting for WhatsApp login...")
        logged_in = await self._client.wait_until_logged_in(timeout=120)
        if not logged_in:
            raise RuntimeError(
                "WhatsApp login timed out after 120s. "
                "Make sure the QR code was scanned or the session is valid."
            )
        print("[WhatsAppAdapter] ✅ Logged in — OmniKernal is now listening for messages.\n")

    async def fetch_new_messages(self) -> list[Message]:
        """
        Poll WhatsApp Web for unread messages across all chats.

        Strategy:
          1. _check_unread_chats() — scans the sidebar for unread badges.
          2. For each unread chat, open it → collect_messages() → close it.
          3. Filter out already-processed messages via _processed_msg_ids.
        """
        result: list[Message] = []

        async with self._browser_lock:
            try:
                # Step 1: find chats with unread messages (sidebar sweep)
                unread_chats = await self._client.chat_manager._check_unread_chats(debug=False)
            except Exception as e:
                print(f"[WhatsAppAdapter] Warning: unread chat scan failed: {e}")
                return []

            for chat_info in unread_chats:
                chat_name: str = chat_info.get("name") or ""
                if not chat_name:
                    continue

                try:
                    # Step 2: open the chat to make its messages visible
                    opened = await self._client.open(chat_name)
                    if not opened:
                        print(f"[WhatsAppAdapter] Could not open chat: {chat_name!r}")
                        continue

                    # Small wait for messages to render in the DOM
                    await asyncio.sleep(0.5)

                    # Step 3: collect all visible messages in this chat
                    raw_messages = await self._client.collect_messages()

                    # Step 4: parse, deduplicate, filter
                    for msg in raw_messages:
                        if not isinstance(msg, WhatsplayMessage):
                            continue

                        # Skip outgoing (our own) messages
                        if getattr(msg, "is_outgoing", False):
                            continue

                        # Build a stable dedup ID
                        raw_text = getattr(msg, "text", "") or ""
                        # Strip trailing WhatsApp timestamp that whatsplay concatenates
                        # onto the text (e.g. "!sys_plugins6:31 PM" → "!sys_plugins")
                        text = _strip_wa_timestamp(raw_text)
                        sender = getattr(msg, "sender", chat_name) or chat_name
                        ts = getattr(msg, "timestamp", None)
                        msg_id = (
                            getattr(msg, "msg_id", None)
                            or f"{sender}:{text}:{ts}"
                        )

                        if msg_id in self._processed_msg_ids:
                            continue
                        self._processed_msg_ids.add(msg_id)

                        # Skip empty messages (after timestamp strip)
                        if not text.strip():
                            continue

                        user = User(
                            id=sender,
                            display_name=sender,
                            platform=self._platform_name,
                        )
                        parsed = Message(
                            id=msg_id,
                            raw_text=text,
                            user=user,
                            timestamp=ts or datetime.now(timezone.utc),
                            platform=self._platform_name,
                        )
                        result.append(parsed)
                        print(f"[WhatsAppAdapter] 📨 New message from {sender!r}: {text!r}")

                except Exception as e:
                    print(f"[WhatsAppAdapter] Error processing chat {chat_name!r}: {e}")
                finally:
                    # Always close the chat after reading so the next poll starts clean
                    try:
                        await self._client.chat_manager.close()
                    except Exception:
                        pass

        return result

    async def send_message(self, to: str, content: str) -> None:
        """
        Send a text reply to a chat identified by `to` (contact/chat name).
        Acquires the browser lock so it doesn't race against the poll sweep.
        """
        async with self._browser_lock:
            try:
                success = await self._client.send_message(to, content)
                if success:
                    print(f"[WhatsAppAdapter] ✅ Reply sent to {to!r}")
                else:
                    print(f"[WhatsAppAdapter] ⚠️  send_message returned False for {to!r}")
            except Exception as e:
                print(f"[WhatsAppAdapter] ❌ Failed to send to {to!r}: {e}")

    async def disconnect(self) -> None:
        """
        Tear down the Playwright browser session cleanly.
        Session is already persisted to disk by LocalProfileAuth.
        """
        print("[WhatsAppAdapter] Disconnecting...")
        try:
            await self._client.stop()
        except Exception as e:
            print(f"[WhatsAppAdapter] Warning during disconnect: {e}")

        # Cancel the background start task if still running
        start_task = getattr(self, "_start_task", None)
        if start_task and not start_task.done():
            start_task.cancel()
            try:
                await start_task
            except (asyncio.CancelledError, Exception):
                pass

        print("[WhatsAppAdapter] 🔌 Browser closed. Session saved — no QR needed next run.")
