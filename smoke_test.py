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
from src.core.loader import MinimalLoader
from src.core.contracts.message import Message
from src.core.contracts.user import User
from src.core.contracts.command_result import CommandResult

# Mock handler for the smoke test
async def mock_echo_handler(args: dict, ctx):
    """Simple echo handler for testing."""
    text = args.get("text", "")
    return CommandResult.success(reply=f"Echo: {text}")

class ConsoleMockAdapter:
    def __init__(self):
        self.platform_name = "console_mock"
        self._sent = []
        self._queue = [
            Message(
                id="m1",
                raw_text="!echo DB-backed Phase 2 is Working!",
                user=User(id="admin", display_name="Admin", platform="console", role="admin"),
                timestamp=datetime.now(),
                platform="console"
            )
        ]

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
        
        print("[Core] Registering test commands in DB...")
        await MinimalLoader.register_mock_commands(repo)
        
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
            print("\nΓ£à SMOKE TEST PASSED: Database-backed Engine successfully processed the message!")
        else:
            print("\nΓ¥î SMOKE TEST FAILED: No reply generated.")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
