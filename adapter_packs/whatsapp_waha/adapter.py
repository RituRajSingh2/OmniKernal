"""
WhatsAppWahaAdapter — Full Implementation (Phase 7)

Implements the PlatformAdapter hook contract using WAHA (WhatsApp HTTP API).
WAHA runs as a Docker container exposing a REST API at http://localhost:3000.

Architecture vs. Playwright adapter:
  Playwright: Browser DOM automation → slow, brittle, timestamp parsing hacks
  WAHA:       Pure HTTP/JSON REST API → fast, reliable, clean message payloads

Key design decisions:
  - Polling via GET /api/messages with ?limit + timestamp tracking.
    WAHA docs recommend webhooks for production, but polling fits our
    existing PlatformAdapter ABC (fetch_new_messages) without changes.
  - chatId format: WhatsApp uses "<phone_number>@c.us" for individuals
    and "<group_id>@g.us" for groups.
  - Session lifecycle: create → start → WORKING → use → stop.
    Session is NOT auto-deleted on stop — WAHA persists auth state in
    its Docker volume across restarts (no QR re-scan needed).
  - API key: passed via X-Api-Key header, read from env var WAHA_API_KEY.
  - fromMe filtering: WAHA's GET /api/messages returns ALL messages
    (sent + received). We filter fromMe=True to skip our own replies.

Setup requirements:
  1. Docker installed
  2. Run: docker run -d -p 3000:3000 devlikeapro/waha
  3. Open http://localhost:3000/dashboard → scan QR once
  4. Set WAHA_API_KEY env var if auth is enabled (default: no auth)
  5. Run: uv run python test_waha.py
"""

import asyncio
import os
from datetime import datetime, timezone

import aiohttp

from src.core.contracts.message import Message
from src.core.contracts.user import User
from src.core.interfaces.platform_adapter import PlatformAdapter


# ── Constants ──────────────────────────────────────────────────────────────
_DEFAULT_API_URL    = "http://localhost:3000"
_DEFAULT_SESSION    = "default"
_POLL_LIMIT         = 100          # messages per GET /api/messages call
_SESSION_WAIT_SECS  = 120          # max seconds to wait for WORKING state
_POLL_INTERVAL_SECS = 1.0          # how often to check session status during boot


class WhatsAppWahaAdapter(PlatformAdapter):
    """
    HTTP REST adapter for WhatsApp Web using WAHA (WhatsApp HTTP API).

    Implements the PlatformAdapter hook contract:
      connect() → fetch_new_messages() loop → send_message() → disconnect()

    Args:
        api_url:      Base URL of the WAHA server. Default: http://localhost:3000
        session_name: WAHA session identifier. Default: "default"
        api_key:      X-Api-Key header value. Reads WAHA_API_KEY env var if
                      not provided. Leave blank if WAHA auth is disabled.
    """

    def __init__(
        self,
        api_url: str = _DEFAULT_API_URL,
        session_name: str = _DEFAULT_SESSION,
        api_key: str | None = None,
    ) -> None:
        self._platform_name = "whatsapp"
        self._api_url       = api_url.rstrip("/")
        self._session_name  = session_name
        self._api_key       = api_key or os.getenv("WAHA_API_KEY", "")

        # HTTP client (created lazily in connect())
        self._http: aiohttp.ClientSession | None = None

        # Timestamp of last seen message — used to filter already-processed
        # messages on the next poll. WAHA returns timestamps as Unix ints.
        self._last_seen_ts: int = 0

        # Secondary dedup by message ID for robustness
        self._processed_ids: set[str] = set()

    # ── Internal helpers ────────────────────────────────────────────────────

    @property
    def platform_name(self) -> str:
        return self._platform_name

    def _headers(self) -> dict[str, str]:
        """Build request headers, injecting API key if configured."""
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._api_key:
            h["X-Api-Key"] = self._api_key
        return h

    def _url(self, path: str) -> str:
        """Construct a full URL from a relative path."""
        return f"{self._api_url}{path}"

    async def _get(self, path: str, params: dict | None = None) -> dict | list | None:
        """Perform a GET request. Returns parsed JSON or None on error."""
        try:
            async with self._http.get(
                self._url(path), headers=self._headers(), params=params
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                body = await resp.text()
                print(f"[WahaAdapter] GET {path} → {resp.status}: {body[:200]}")
                return None
        except aiohttp.ClientConnectorError:
            print(f"[WahaAdapter] ❌ Cannot reach WAHA at {self._api_url}. Is Docker running?")
            return None
        except Exception as e:
            print(f"[WahaAdapter] GET {path} failed: {e}")
            return None

    async def _post(self, path: str, payload: dict) -> dict | None:
        """Perform a POST request. Returns parsed JSON or None on error."""
        try:
            async with self._http.post(
                self._url(path), headers=self._headers(), json=payload
            ) as resp:
                if resp.status in (200, 201):
                    return await resp.json()
                body = await resp.text()
                print(f"[WahaAdapter] POST {path} → {resp.status}: {body[:200]}")
                return None
        except aiohttp.ClientConnectorError:
            print(f"[WahaAdapter] ❌ Cannot reach WAHA at {self._api_url}. Is Docker running?")
            return None
        except Exception as e:
            print(f"[WahaAdapter] POST {path} failed: {e}")
            return None

    # ── Session management ──────────────────────────────────────────────────

    async def _get_session_status(self) -> str | None:
        """
        Returns the current session status string, e.g. 'WORKING', 'SCAN_QR_CODE'.
        Returns None if session doesn't exist or the request fails.
        """
        data = await self._get(f"/api/sessions/{self._session_name}")
        if data and isinstance(data, dict):
            return data.get("status")
        return None

    async def _ensure_session(self) -> None:
        """
        Idempotently start the WAHA session.
        If the session doesn't exist, create it.
        If it already exists but is STOPPED, start it.
        If already WORKING, do nothing.
        """
        status = await self._get_session_status()

        if status is None:
            # Session doesn't exist — create + start it
            print(f"[WahaAdapter] Creating session '{self._session_name}'...")
            await self._post("/api/sessions", {"name": self._session_name})
        elif status in ("STOPPED", "FAILED"):
            # Session exists but not running — start it
            print(f"[WahaAdapter] Starting session '{self._session_name}' (was {status})...")
            await self._post(f"/api/sessions/{self._session_name}/start", {})
        elif status == "WORKING":
            print(f"[WahaAdapter] ✅ Session '{self._session_name}' already WORKING.")
            return
        else:
            print(f"[WahaAdapter] Session status: {status}")

    async def _wait_for_working(self) -> None:
        """
        Poll session status until WORKING or timeout.
        During SCAN_QR_CODE, print instructions.
        """
        print(f"[WahaAdapter] Waiting for session to reach WORKING state...")
        print(f"[WahaAdapter] 👉 Open http://localhost:3000/dashboard to scan QR if prompted.\n")

        qr_printed = False
        elapsed = 0.0

        while elapsed < _SESSION_WAIT_SECS:
            status = await self._get_session_status()

            if status == "WORKING":
                print(f"[WahaAdapter] ✅ Session WORKING — OmniKernal is now listening.")
                return

            if status == "SCAN_QR_CODE" and not qr_printed:
                print(f"[WahaAdapter] 📱 Scan QR at http://localhost:3000/dashboard")
                print(f"[WahaAdapter]    or GET http://localhost:3000/api/{self._session_name}/auth/qr")
                qr_printed = True

            if status == "FAILED":
                raise RuntimeError(
                    f"WAHA session '{self._session_name}' FAILED. "
                    "Try: docker restart <waha-container> and scan QR again."
                )

            await asyncio.sleep(_POLL_INTERVAL_SECS)
            elapsed += _POLL_INTERVAL_SECS

        raise RuntimeError(
            f"Timed out after {_SESSION_WAIT_SECS}s waiting for WAHA session. "
            "Check http://localhost:3000/dashboard"
        )

    # ── PlatformAdapter ABC ─────────────────────────────────────────────────

    async def connect(self) -> None:
        """
        Start the aiohttp session, ensure the WAHA session is running,
        and wait until it reaches WORKING state (QR scan if needed).

        Sets self._last_seen_ts to now so we only process future messages.
        """
        self._http = aiohttp.ClientSession()

        try:
            await self._ensure_session()
            await self._wait_for_working()
        except Exception:
            await self._http.close()
            self._http = None
            raise

        # Seed timestamp — only process messages arriving AFTER this point
        self._last_seen_ts = int(datetime.now(timezone.utc).timestamp())
        print(f"[WahaAdapter] Seeded timestamp: {self._last_seen_ts} (ignoring older messages)\n")

    async def fetch_new_messages(self) -> list[Message]:
        """
        Poll GET /api/messages for new incoming messages since last check.

        WAHA returns messages in ascending timestamp order.
        We filter:
          - fromMe=True  (our own sent messages)
          - Already seen message IDs
          - Messages older than _last_seen_ts
        """
        if not self._http:
            return []

        result: list[Message] = []

        try:
            # 1. Fetch all chats to find which ones have unread messages
            chats = await self._get(f"/api/{self._session_name}/chats")
            if not isinstance(chats, list):
                return []
            
            unread_chats = [c for c in chats if c.get("unreadCount", 0) > 0]
            if not unread_chats:
                return []

            latest_ts = self._last_seen_ts

            # 2. For each unread chat, fetch its recent messages
            for chat in unread_chats:
                chat_id_obj = chat.get("id", {})
                chat_id = chat_id_obj.get("_serialized") or chat_id_obj.get("user")
                unread_count = chat.get("unreadCount", 1)

                if not chat_id:
                    continue

                params = {
                    "session": self._session_name,
                    "chatId": chat_id,
                    "limit": str(max(unread_count, 10)),  # grab a bit of context just in case
                }
                messages_data = await self._get("/api/messages", params=params)
                
                # WAHA /messages returns an array of message objects
                if isinstance(messages_data, list):
                    for item in messages_data:
                        if not isinstance(item, dict):
                            continue
                            
                        raw_id = item.get("id", "")
                        if isinstance(raw_id, dict):
                            msg_id = raw_id.get("_serialized", "") or str(raw_id)
                        else:
                            msg_id = str(raw_id)
                            
                        from_me   = item.get("fromMe", False)
                        timestamp = item.get("timestamp", 0)   # Unix int
                        body      = item.get("body", "") or ""
                        
                        # Sender identification: groups vs direct messages
                        from_field = item.get("from", chat_id)
                        
                        # In WAHA, group messages put the sender's phone in `participant` or `author` inside `lastMessage._data`
                        author = item.get("author", "")
                        sender_id = author if author else from_field

                        # Skip: outgoing, already processed, older than boot time
                        if from_me:
                            continue
                        if msg_id in self._processed_ids:
                            continue
                        # If a message is too old we still process it if it's unread, 
                        # but we can honor the boot timestamp limit
                        if timestamp <= self._last_seen_ts:
                            continue

                        self._processed_ids.add(msg_id)

                        if timestamp > latest_ts:
                            latest_ts = timestamp

                        body = body.strip()
                        if not body:
                            continue

                        # Parse display name
                        display = sender_id.split("@")[0] if isinstance(sender_id, str) and "@" in sender_id else str(sender_id)

                        user = User(
                            id=chat_id,  # Ensure replies go to the chat itself (important for groups)
                            display_name=display,
                            platform=self._platform_name,
                        )
                        msg = Message(
                            id=str(msg_id),
                            raw_text=body,
                            user=user,
                            timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                            platform=self._platform_name,
                        )
                        result.append(msg)
                        print(f"[WahaAdapter] 📨 {display}: {body!r}")

                # 3. Mark the chat as seen so we don't fetch it again on next poll
                await self._post("/api/sendSeen", {
                    "session": self._session_name,
                    "chatId": chat_id
                })

        except Exception as e:
            import traceback
            print(f"[WahaAdapter] Warning: fetch failed: {e}")
            traceback.print_exc()
            return []

        # Advance the watermark so next poll skips these
        self._last_seen_ts = latest_ts
        return result

    async def send_message(self, to: str, content: str) -> None:
        """
        Send a text message via POST /api/sendText.

        Args:
            to:      Sender identifier from Message.user.id — already in
                     WhatsApp chatId format (e.g. "911234567890@c.us").
            content: Reply text to send.
        """
        if not self._http:
            print("[WahaAdapter] ❌ Not connected — cannot send message.")
            return

        payload = {
            "session": self._session_name,
            "chatId":  to,
            "text":    content,
        }
        resp = await self._post("/api/sendText", payload)

        if resp:
            print(f"[WahaAdapter] ✅ Reply sent to {to!r}")
        else:
            print(f"[WahaAdapter] ⚠️  send_message failed for {to!r}")

    async def disconnect(self) -> None:
        """
        Stop the WAHA session and close the HTTP client.

        Note: WAHA persists auth state in Docker volumes — stopping the
        session does NOT delete the WhatsApp login. Next run reconnects
        instantly without a QR scan.
        """
        print("[WahaAdapter] Disconnecting...")

        if self._http:
            try:
                await self._post(
                    f"/api/sessions/{self._session_name}/stop", {}
                )
                print(f"[WahaAdapter] Session '{self._session_name}' stopped.")
            except Exception as e:
                print(f"[WahaAdapter] Warning during session stop: {e}")
            finally:
                await self._http.close()
                self._http = None

        print("[WahaAdapter] 🔌 Disconnected. Auth persisted in Docker volume — no QR next run.")
