"""
OmniKernal — Baileys Integration Test Runner
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("."))

from src.core.engine import OmniKernal
from src.database.session import async_session_factory, init_db
from src.database.repository import OmniRepository
from adapter_packs.whatsapp_baileys.adapter import WhatsAppBaileysAdapter

async def main() -> None:
    print("🚀 Booting OmniKernal with Baileys Adapter (Socket Bridge)...")
    await init_db()

    adapter = WhatsAppBaileysAdapter(
        bridge_port=3001,
        session_name="default",
    )

    async with async_session_factory() as session:
        repo = OmniRepository(session)
        core = OmniKernal(
            adapter=adapter,
            repository=repo,
            session_factory=async_session_factory,
            profile_name="baileys_test",
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
