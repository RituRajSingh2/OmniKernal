"""
OmniKernal — Smoke Test (Phase 4: Adapter Pack Discovery)

Demonstrates the full Core Engine loop using AdapterLoader:
1. Discovers the console_mock adapter pack from adapter_packs/
2. Boots the engine with the loaded adapter
3. Injects a simulated message
4. Runs the pipeline: Sanitize -> Parse -> Route -> Execute -> Reply
"""

import asyncio
from src.core.engine import OmniKernal
from src.database.session import async_session_factory, ensure_db_initialized  # BUG 43
from src.database.repository import OmniRepository
from src.adapters.loader import AdapterLoader


async def run_smoke_test():
    # 1. Initialize DB and Repository (BUG 43: use idempotent helper)
    print("[Core] Initializing Database...")
    await ensure_db_initialized()

    async with async_session_factory() as session:
        repo = OmniRepository(session)

        # 2. Discover and load adapter from adapter_packs/
        print("[Core] Loading adapter pack: console_mock...")
        loader = AdapterLoader()
        adapter = loader.load("console_mock")

        # 3. Inject a test message
        adapter.inject_message("!echo Declarative Phase 4 is Working!")

        # 4. Boot the engine
        engine = OmniKernal(adapter, repo)

        print("[Core] Starting Engine...")
        engine_task = asyncio.create_task(engine.start())

        # Wait for message processing
        await asyncio.sleep(2)

        print("[Core] Stopping Engine...")
        await engine.stop()
        await engine_task

        if adapter.sent_messages:
            print("\n[PASS] SMOKE TEST PASSED: Adapter Pack discovery + Engine pipeline working!")
        else:
            print("\n[FAIL] SMOKE TEST FAILED: No reply generated.")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
