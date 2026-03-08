import asyncio
import os
import sys

# Ensure src is in path
sys.path.insert(0, os.path.abspath("."))

from src.core.engine import OmniKernal
from src.database.session import async_session_factory, init_db
from src.database.repository import OmniRepository
from adapter_packs.whatsapp_playwright.adapter import WhatsAppPlaywrightAdapter


async def main():
    print("🚀 Booting OmniKernal with WhatsApp Playwright Adapter...")
    
    try:
        # Initialize Core with proper session and repo (fixing BaseDir/TypeError)
        await init_db()
        async with async_session_factory() as session:
            repo = OmniRepository(session)
            core = OmniKernal(
                adapter=WhatsAppPlaywrightAdapter(),
                repository=repo,
                session_factory=async_session_factory,
            )
            
            await core.start()
    except KeyboardInterrupt:
        print("\nStopping...")
        await adapter.disconnect()
        await core.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
