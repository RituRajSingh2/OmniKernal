import asyncio
from typing import TYPE_CHECKING, Optional
from datetime import datetime, timezone
from src.core.logger import core_logger
from src.security.sanitizer import CommandSanitizer
from src.security.watchdog import ApiWatchdog          # BUG 4: was missing
from src.core.dispatcher import EventDispatcher
from src.core.loader import PluginEngine
from src.database.session import init_db
from src.profiles.manager import ProfileManager
from src.modes.mode_manager import ModeManager

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

    def __init__(
        self,
        adapter: "PlatformAdapter",
        repository: "OmniRepository",
        profile_name: str = "main",
        profiles_dir: str = "profiles",
        mode: str = "self",
    ):
        self.adapter = adapter
        self.repository = repository
        self.profile_name = profile_name
        self.mode = mode
        self.profile_manager = ProfileManager(profiles_dir)
        self.mode_manager = ModeManager()
        self.dispatcher: Optional[EventDispatcher] = None   # BUG 12: explicit type
        self.watchdog = ApiWatchdog(repository)             # BUG 4: wire watchdog
        self.headless: bool = False
        self.logger = core_logger.bind(profile=profile_name)
        self.is_running = False
        self._stop_event = asyncio.Event()

    async def start(self):
        """Boot sequence."""
        self.logger.info(
            f"Booting OmniKernal for platform: {self.adapter.platform_name} "
            f"[mode={self.mode}]"
        )

        # Initialize DB
        await init_db()

        # Profile Activation (Phase 5)
        if not self.profile_manager.get_profile(self.profile_name):
            self.logger.info(f"First run: creating profile '{self.profile_name}'.")
            self.profile_manager.create(self.profile_name, self.adapter.platform_name)

        meta = self.profile_manager.activate(self.profile_name)
        self.headless = meta.get("headless", False)
        self.logger.info(
            f"Profile '{self.profile_name}' activated. headless={self.headless}"
        )

        # Plugin Discovery (Phase 3)
        loader = PluginEngine(self.repository)
        await loader.discover_and_load()

        self.dispatcher = EventDispatcher(self.repository, logger=self.logger)

        try:
            await self.adapter.connect()
            self.is_running = True
            self.logger.info("Adapter connected. Starting execution mode.")

            # Phase 6: delegate polling to ModeManager
            await self.mode_manager.start(self.mode, self, self.adapter)
            # Wait until engine is stopped
            await self._stop_event.wait()
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

        # Stop execution mode (Phase 6)
        await self.mode_manager.stop()

        await self.adapter.disconnect()

        # Profile Deactivation (Phase 5) — release PID lock
        try:
            self.profile_manager.deactivate(self.profile_name)
        except Exception as e:
            self.logger.warning(f"Profile deactivation warning: {e}")

        self.logger.info("Shutdown complete.")

    async def process(self, msg: "Message") -> None:
        """Public processing pipeline — called by SelfMode and CoopMode."""

        # BUG 12: guard against dispatcher not yet initialised (race in early stop())
        if self.dispatcher is None:
            self.logger.warning("process() called before dispatcher was initialised.")
            return

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

        # BUG 1 fix: was `result.success` — that attribute does not exist; `.ok` is correct
        # BUG 4 fix: record API failure in watchdog when handler reports one
        elif result and not result.ok:
            self.logger.error(f"Command failed: {result.error_reason}")
            if result.api_url:
                cmd_name = clean_text.split(" ")[0][1:]
                tool = await self.repository.get_tool_by_command(cmd_name)
                if tool:
                    await self.watchdog.record_failure(
                        result.api_url, tool.id, result.error_reason or "unknown"
                    )
