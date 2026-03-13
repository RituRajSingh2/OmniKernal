"""
OmniKernal — WAHA Integration Test Runner

Boots OmniKernal with the WhatsAppWahaAdapter (HTTP REST).

Prerequisites:
  1. Docker: docker run -d -p 3000:3000 devlikeapro/waha
  2. Open http://localhost:3000/dashboard → scan QR (first run only)
  3. Optional: set WAHA_API_KEY env var if auth enabled on WAHA

Test: send "!devkit_ping" from WhatsApp → should receive 🏓 PONG reply.

Usage:
    uv run python test_waha.py
    WAHA_URL=http://localhost:3000 uv run python test_waha.py

Comparison vs. Playwright:
  - No Chromium browser — pure HTTP JSON
  - No DOM scraping, no timestamp-concat bug
  - Faster message detection, lower CPU
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from src.core.engine import OmniKernal
from src.database.session import async_session_factory, init_db
from src.database.repository import OmniRepository
from adapter_packs.whatsapp_waha.adapter import WhatsAppWahaAdapter

WAHA_URL     = os.getenv("WAHA_URL", "http://localhost:3000")
SESSION_NAME = os.getenv("WAHA_SESSION", "default")
WAHA_API_KEY = os.getenv("WAHA_API_KEY", "omnikernal_secret")

# Ensure the adapter can pick it up via env variable if we pass it down
if "WAHA_API_KEY" not in os.environ:
    os.environ["WAHA_API_KEY"] = WAHA_API_KEY


async def main() -> None:
    print("🚀 Booting OmniKernal with WAHA Adapter (HTTP REST)...")
    print(f"   WAHA server : {WAHA_URL}")
    print(f"   Session     : {SESSION_NAME}")
    print(f"   Dashboard   : {WAHA_URL}/dashboard\n")

    await init_db()

    adapter = WhatsAppWahaAdapter(
        api_url=WAHA_URL,
        session_name=SESSION_NAME,
    )

    async with async_session_factory() as session:
        repo = OmniRepository(session)
        core = OmniKernal(
            adapter=adapter,
            repository=repo,
            session_factory=async_session_factory,
            profile_name="waha_test",
            mode="self",
        )

        try:
            await core.start()
        except KeyboardInterrupt:
            pass
        finally:
            if core.is_running:
                await core.stop()
            print("\n✅ OmniKernal stopped cleanly.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
