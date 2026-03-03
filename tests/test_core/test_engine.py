import pytest
import asyncio
from datetime import datetime
from src.core.engine import OmniKernal
from src.core.router import CommandRouter
from src.core.loader import MinimalLoader
from src.core.contracts.message import Message
from src.core.contracts.user import User

class MockAdapter:
    def __init__(self):
        self.platform_name = "mock"
        self.sent_messages = []
        self._messages_to_return = [
            Message(
                id="msg1",
                raw_text="!echo hello integration",
                user=User(id="user1", display_name="Test User", platform="mock"),
                timestamp=datetime.now(),
                platform="mock"
            )
        ]

    async def connect(self): pass
    async def disconnect(self): pass

    async def fetch_new_messages(self):
        # Return messages only once then clear to stop the loop later
        msgs = self._messages_to_return
        self._messages_to_return = []
        return msgs

    async def send_message(self, to: str, content: str):
        self.sent_messages.append((to, content))

@pytest.mark.asyncio
async def test_engine_integration_loop():
    # Setup
    router = CommandRouter()
    MinimalLoader.register_mock_commands(router)
    
    adapter = MockAdapter()
    engine = OmniKernal(adapter, router)
    
    # Run for a very short time
    # We cheat a bit by making engine.is_running False after one cycle
    # or by wrapping it in a timeout
    
    task = asyncio.create_task(engine.start())
    
    # Wait for the message to be processed (it polls every 0.5s)
    await asyncio.sleep(1.0)
    
    await engine.stop()
    await task
    
    # Verify
    assert len(adapter.sent_messages) == 1
    to, content = adapter.sent_messages[0]
    assert to == "user1"
    assert "Echo: hello integration" in content
