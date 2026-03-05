import asyncio
from typing import TYPE_CHECKING
from datetime import datetime, timezone
from src.core.logger import core_logger
from src.security.sanitizer import CommandSanitizer
from src.core.dispatcher import EventDispatcher
from src.core.loader import PluginEngine
from src.database.session import init_db

if TYPE_CHECKING:
    from src.core.interfaces.platform_adapter import PlatformAdapter
    from src.database.repository import OmniRepository
    from src.core.contracts.message import Message
    from src.core.contracts.user import User

class OmniKernal:
    """
    The beating heart of OmniKernal.
    Platform-agnostic and logic-agnostic.
    """

    def __init__(self, adapter: "PlatformAdapter", repository: "OmniRepository", profile_name: str = "main"):
        self.adapter = adapter
        self.repository = repository
        self.dispatcher = None # Set in start()
        self.profile_name = profile_name
        self.logger = core_logger.bind(profile=profile_name)
        self.is_running = False
        self._stop_event = asyncio.Event()

    async def start(self):
        """Boot sequence."""
        self.logger.info(f"Booting OmniKernal for platform: {self.adapter.platform_name}")
        
        # Initialize DB
        await init_db()
        
        # Plugin Discovery (Phase 3)
        loader = PluginEngine(self.repository)
        await loader.discover_and_load()
        
        self.dispatcher = EventDispatcher(self.repository, logger=self.logger)
        
        try:
            await self.adapter.connect()
            self.is_running = True
            self.logger.info("Adapter connected. Entering poll loop.")
            
            await self._poll_loop()
        except Exception as e:
            self.logger.error(f"Boot failed: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Graceful shutdown."""
        if not self.is_running:
            return

        self.logger.info("Stopping OmniKernal...")
        self.is_running = False
        self._stop_event.set()
        await self.adapter.disconnect()
        self.logger.info("Shutdown complete.")

    async def _poll_loop(self):
        """
        The main execution heart.
        Polls the adapter for messages and process them.
        """
        while self.is_running:
            try:
                messages = await self.adapter.fetch_new_messages()
                
                for msg in messages:
                    await self._process_message(msg)
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.warning(f"Error in poll loop: {e}")
                await asyncio.sleep(2)

    async def _process_message(self, msg: "Message"):
        """The processing pipeline."""
        self.logger.debug(f"Received message from {msg.user.id}: {msg.raw_text}")
        
        # 1. Sanitize
        clean_text = CommandSanitizer.sanitize(msg.raw_text)
        
        if not clean_text or not clean_text.startswith("!"):
            return

        # 2. Dispatch & Execute
        start_time = datetime.now(timezone.utc)
        result = await self.dispatcher.dispatch(clean_text, msg.user)
        duration_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
        
        # 3. Log Execution to DB
        if result:
            await self.repository.log_execution(
                user_id=msg.user.id,
                platform=msg.platform,
                command_name=clean_text.split(" ")[0][1:],
                raw_input=msg.raw_text,
                success=result.ok,
                response_time_ms=duration_ms,
                error_reason=result.error_reason
            )
        
        # 4. Handle Reply
        if result and result.reply:
            self.logger.info(f"Command succeeded. Sending reply to {msg.user.id}")
            await self.adapter.send_message(msg.user.id, result.reply)
        elif result and not result.success:
            self.logger.error(f"Command failed: {result.error_reason}")
            # Optional: send error to user
            # await self.adapter.send_message(msg.user.id, f"Γ¥î Error: {result.error_reason}")
