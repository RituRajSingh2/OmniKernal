"""
OmniKernal Phase 1 ΓÇö Smoke Test

This script demonstrates the full Core Engine loop:
1. Boots the engine with a ConsoleAdapter (MOCKED)
2. Injects a simulated message
3. Runs the pipeline: Sanitize -> Parse -> Route -> Execute -> Reply
"""

import asyncio
from datetime import datetime
from src.core.engine import OmniKernal
from src.database.session import async_session_factory, init_db
from src.database.repository import OmniRepository
from src.core.contracts.message import Message
from src.core.contracts.user import User
from src.core.contracts.command_result import CommandResult

from src.core.interfaces.platform_adapter import PlatformAdapter

class ConsoleMockAdapter(PlatformAdapter):
    def __init__(self):
        self._platform_name = "console_mock"
        self._sent = []
        self._queue = [
            Message(
                id="m1",
                raw_text="!echo Declarative Phase 3 is Working!",
                user=User(id="admin", display_name="Admin", platform="console", role="admin"),
                timestamp=datetime.now(),
                platform="console"
            )
        ]

    @property
    def platform_name(self) -> str:
        return self._platform_name

    async def connect(self):
        print("[Adapter] Connected to virtual console.")

    async def disconnect(self):
        print("[Adapter] Disconnected.")

    async def fetch_new_messages(self):
        if self._queue:
            msg = self._queue.pop(0)
            return [msg]
        return []

    async def send_message(self, to: str, content: str):
        print(f"\n[OUTPUT to {to}] -> {content}\n")
        self._sent.append(content)

async def run_smoke_test():
    # 1. Initialize DB and Repository
    print("[Core] Initializing Database...")
    await init_db()
    
    async with async_session_factory() as session:
        repo = OmniRepository(session)
        
        adapter = ConsoleMockAdapter()
        engine = OmniKernal(adapter, repo)
        
        print("[Core] Starting Engine...")
        engine_task = asyncio.create_task(engine.start())
        
        # Wait for message processing
        await asyncio.sleep(2)
        
        print("[Core] Stopping Engine...")
        await engine.stop()
        await engine_task
        
        if adapter._sent:
            print("\n[PASS] SMOKE TEST PASSED: Database-backed Engine successfully processed the message!")
        else:
            print("\n[FAIL] SMOKE TEST FAILED: No reply generated.")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
