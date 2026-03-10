"""
OmniKernal — WhatsApp Playwright Integration Test Runner

Boots OmniKernal with the WhatsAppPlaywrightAdapter.

First run:  Opens headed Chromium → scan QR → session auto-saved to
            profiles/whatsapp_test/wa_session/

Next runs:  Session restored automatically — no QR needed.

Test command: send "!sys_plugins" from any WhatsApp chat.
Expected reply: list of all registered plugins.

Usage:
    uv run python test_playwright.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from src.core.engine import OmniKernal
from src.database.session import async_session_factory, init_db
from src.database.repository import OmniRepository
from adapter_packs.whatsapp_playwright.adapter import WhatsAppPlaywrightAdapter

PROFILE_NAME = "whatsapp_test"


async def main() -> None:
    print("🚀 Booting OmniKernal with WhatsApp Playwright Adapter...")
    print(f"   Session will be saved to: profiles/{PROFILE_NAME}/wa_session/\n")

    await init_db()

    adapter = WhatsAppPlaywrightAdapter(profile_name=PROFILE_NAME, headless=False)

    async with async_session_factory() as session:
        repo = OmniRepository(session)
        core = OmniKernal(
            adapter=adapter,
            repository=repo,
            session_factory=async_session_factory,
            profile_name=PROFILE_NAME,
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
