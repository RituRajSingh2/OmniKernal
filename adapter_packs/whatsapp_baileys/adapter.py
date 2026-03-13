import asyncio
import os
import sys
import subprocess
from datetime import datetime, timezone

import aiohttp

from src.core.contracts.message import Message
from src.core.contracts.user import User
from src.core.interfaces.platform_adapter import PlatformAdapter


class WhatsAppBaileysAdapter(PlatformAdapter):
    """
    Platform adapter that connects to WhatsApp Web via a local Node.js bridge.
    The bridge uses the @whiskeysockets/baileys library under the hood.
    """

    def __init__(self, bridge_port: int = 3001, session_name: str = "default"):
        self._bridge_port = bridge_port
        self._session_name = session_name
        self._api_url = f"http://127.0.0.1:{bridge_port}"
        self._bridge_proc: subprocess.Popen | None = None
        self._http: aiohttp.ClientSession | None = None
        
        # Track our last seed to only fetch messages arriving AFTER boot
        self._boot_ts = int(datetime.now(timezone.utc).timestamp())
        self._processed_ids: set[str] = set()

    @property
    def platform_name(self) -> str:
        return "whatsapp"
        
    async def connect(self) -> None:
        print(f"[BaileysAdapter] Starting Node.js Baileys Bridge on port {self._bridge_port}...")
        
        adapter_dir = os.path.dirname(os.path.abspath(__file__))
        script_path = os.path.join(adapter_dir, "baileys_bridge.js")
        
        env = os.environ.copy()
        env["BRIDGE_PORT"] = str(self._bridge_port)
        env["SESSION_NAME"] = self._session_name
        
        # Run node bridge as subprocess
        self._bridge_proc = subprocess.Popen(
            ["node", script_path],
            env=env,
            cwd=adapter_dir,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        
        self._http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
        
        # Wait for HTTP server to come up
        server_up = False
        for _ in range(30):
            try:
                async with self._http.get(f"{self._api_url}/status") as resp:
                    if resp.status == 200:
                        server_up = True
                        break
            except Exception:
                pass
            await asyncio.sleep(1)
            
        if not server_up:
            raise RuntimeError("Timed out waiting for Baileys Node bridge HTTP API to start.")
        
        print("[BaileysAdapter] Waiting for Baileys to reach WORKING state...")
        
        # Wait for WhatsApp Web connection state to become WORKING
        for _ in range(300):
            try:
                async with self._http.get(f"{self._api_url}/status") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        st = data.get("status")
                        if st == "WORKING":
                            print("[BaileysAdapter] ✅ Session WORKING — OmniKernal is now listening.")
                            print(f"[BaileysAdapter] Seeded timestamp: {self._boot_ts} (ignoring older messages)\n")
                            return
                        elif st == "SCAN_QR_CODE":
                            pass # The JS script prints the QR directly to stdout
                        elif st == "DISCONNECTED":
                            pass
            except Exception:
                pass
            await asyncio.sleep(2)
            
        raise RuntimeError(f"Timed out waiting for Baileys session to reach WORKING.")

    async def fetch_new_messages(self) -> list[Message]:
        if not self._http:
            return []

        try:
            async with self._http.get(f"{self._api_url}/messages") as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        except Exception as e:
            print(f"[BaileysAdapter] Warning: fetch failed: {e}")
            return []
            
        msgs_data = data.get("messages", [])
        result = []
        
        for item in msgs_data:
            msg_id = str(item.get("id", ""))
            timestamp = int(item.get("timestamp", 0))
            body = item.get("body", "").strip()
            chat_id = item.get("from")
            sender_id = item.get("sender")
            
            if msg_id in self._processed_ids:
                continue
            if timestamp <= self._boot_ts:
                continue
            if not body:
                continue
                
            self._processed_ids.add(msg_id)
            
            # Extract clean display name
            display = sender_id.split("@")[0] if isinstance(sender_id, str) and "@" in sender_id else str(sender_id)
            
            user = User(
                id=chat_id,  # Ensure we reply to the parent thread constraint
                display_name=display,
                platform=self.platform_name,
            )
            msg = Message(
                id=msg_id,
                raw_text=body,
                user=user,
                timestamp=datetime.fromtimestamp(timestamp, tz=timezone.utc),
                platform=self.platform_name,
            )
            result.append(msg)
            print(f"[BaileysAdapter] 📨 {display}: {body!r}")
            
        return result

    async def send_message(self, to: str, content: str) -> None:
        if not self._http:
            return
            
        try:
            async with self._http.post(f"{self._api_url}/send", json={"to": to, "text": content}) as resp:
                if resp.status == 200:
                    print(f"[BaileysAdapter] ✅ Reply sent to '{to}'")
                else:
                    text = await resp.text()
                    print(f"[BaileysAdapter] ⚠️ Send failed: {resp.status} - {text}")
        except Exception as e:
            print(f"[BaileysAdapter] Error sending message: {e}")

    async def disconnect(self) -> None:
        if self._http:
            await self._http.close()
            self._http = None
        if self._bridge_proc:
            print("[BaileysAdapter] Stopping Node.js Baileys Bridge...")
            self._bridge_proc.terminate()
            try:
                self._bridge_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._bridge_proc.kill()
            self._bridge_proc = None
        print("[BaileysAdapter] 🔌 Disconnected.")
