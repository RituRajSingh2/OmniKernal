"""
OmniKernal — Core Engine Lifecycle

Orchestrates the full boot/shutdown sequence and the message processing
pipeline (sanitize → dispatch → log → reply).

BUG 62 fix: OmniKernal now accepts `session_factory` (an async_sessionmaker)
in addition to a top-level `repository`. A fresh OmniRepository is created
*per process() call*, preventing concurrent CoopMode tasks from racing on a
shared AsyncSession and causing SQLAlchemy IllegalStateError.

BUG 53 fix: EventDispatcher.dispatch() now returns a DispatchResult namedtuple
that includes the resolved tool_id. This lets the engine feed the correct id to
ApiWatchdog for regex-triggered commands (previously, the engine tried to
resolve the tool by the raw user trigger, which missed regex routes).
"""

import asyncio
from typing import TYPE_CHECKING, Optional
from datetime import datetime, timezone
from src.core.logger import core_logger
from src.security.sanitizer import CommandSanitizer
from src.security.watchdog import ApiWatchdog          # BUG 4: was missing
from src.core.dispatcher import EventDispatcher
from src.core.loader import PluginEngine
from src.database.session import init_db
from src.database.repository import OmniRepository
from src.profiles.manager import ProfileManager
from src.modes.mode_manager import ModeManager
from src.core.router import RulesCache                 # BUG 68

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import async_sessionmaker
    from src.core.interfaces.platform_adapter import PlatformAdapter
    from src.core.contracts.message import Message
    from src.core.contracts.user import User

class OmniKernal:
    """
    The beating heart of OmniKernal.
    Platform-agnostic and logic-agnostic.

    Args:
        adapter:         The platform adapter to use.
        repository:      A top-level OmniRepository used for boot-time DB ops
                         (plugin registration, profile activation). NOT used for
                         per-message processing.
        session_factory: BUG 62 fix — an async_sessionmaker. If supplied, a fresh
                         OmniRepository is created for each process() call, avoiding
                         session contention in CoopMode. If None, falls back to
                         sharing `repository` (legacy behaviour, single-threaded only).
        profile_name:    Profile directory name to activate on boot.
        profiles_dir:    Root directory containing profile folders.
        mode:            "self" (autonomous) or "coop" (human-in-loop).
    """

    def __init__(
        self,
        adapter: "PlatformAdapter",
        repository: "OmniRepository",
        profile_name: str = "main",
        profiles_dir: str = "profiles",
        mode: str = "self",
        session_factory: Optional["async_sessionmaker"] = None,
    ):
        self.adapter = adapter
        self.repository = repository
        self._session_factory = session_factory                     # BUG 62
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
        self._rules_cache = RulesCache()                 # BUG 68: shared cache container

    # ------------------------------------------------------------------
    # Internal: session-per-request helper (BUG 62)
    # ------------------------------------------------------------------

    def _make_repo(self, session) -> "OmniRepository":
        """Return a fresh repository bound to *session*."""
        return OmniRepository(session)

    # ------------------------------------------------------------------
    # Boot / Shutdown
    # ------------------------------------------------------------------

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
        loader = PluginEngine(self.repository, platform_name=self.adapter.platform_name)
        await loader.discover_and_load()

        self.dispatcher = EventDispatcher(
            self.repository,
            logger=self.logger,
            rules_cache=self._rules_cache  # BUG 68
        )

        try:
            await self.adapter.connect()

            # BUG 46 fix: check is_running AFTER connect returns. If stop() was
            # called while connect() was awaiting, it would have set is_running=False.
            # Without this guard we'd override that and start polling anyway.
            if not self.is_running and self._stop_event.is_set():
                self.logger.warning("stop() was called during adapter.connect(). Aborting boot.")
                return

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
        """Graceful shutdown. BUG 67: Always set stop event to abort boot."""
        self.logger.info("Stopping OmniKernal...")
        was_running = self.is_running
        self.is_running = False
        self._stop_event.set()

        if not was_running:
            # If we weren't fully started yet, we still want to stop
            # but we skip mode_manager/adapter cleanup if they aren't ready.
            self.logger.info("OmniKernal stop() called before full boot. Aborted.")
            return

        # Stop execution mode (Phase 6)
        await self.mode_manager.stop()

        await self.adapter.disconnect()

        # Profile Deactivation (Phase 5) — release PID lock
        try:
            self.profile_manager.deactivate(self.profile_name)
        except Exception as e:
            self.logger.warning(f"Profile deactivation warning: {e}")

        self.logger.info("Shutdown complete.")

    # ------------------------------------------------------------------
    # Message Processing
    # ------------------------------------------------------------------

    async def process(self, msg: "Message") -> None:
        """Public processing pipeline — called by SelfMode and CoopMode.

        BUG 62 fix: If a session_factory was supplied, we create a brand-new
        session (and repository) for this call. CoopMode can therefore invoke
        process() concurrently for multiple approved messages without two tasks
        sharing the same AsyncSession.
        """

        # BUG 12: guard against dispatcher not yet initialised (race in early stop())
        if self.dispatcher is None:
            self.logger.warning("process() called before dispatcher was initialised.")
            return

        self.logger.debug(f"Received message from {msg.user.id}: {msg.raw_text}")

        # 1. Sanitize
        clean_text = CommandSanitizer.sanitize(msg.raw_text)

        if not clean_text or not clean_text.startswith("!"):
            return

        # 2. Get a per-request session/repo (BUG 62 fix)
        if self._session_factory is not None:
            async with self._session_factory() as session:
                await self._process_with_session(clean_text, msg, session)
        else:
            # Fallback: legacy shared repo (safe for SelfMode / sequential flows)
            await self._process_with_session(clean_text, msg, repo=self.repository)

    async def _process_with_session(
        self,
        clean_text: str,
        msg: "Message",
        session=None,
        repo: Optional["OmniRepository"] = None,
    ) -> None:
        """Core pipeline using either a fresh session or an existing repo.

        When session_factory is used (BUG 62 path), we create a new dispatcher
        bound to the fresh session's repo. For the legacy path (no session_factory),
        we re-use self.dispatcher which may have been injected by tests or set
        at boot time.
        """

        if repo is None:
            repo = self._make_repo(session)

        # Use a fresh dispatcher when we have a fresh repo (BUG 62 session path).
        # Reuse self.dispatcher when the legacy no-session path is taken — this
        # preserves test injection of mock dispatchers.
        if session is not None:
            # BUG 68: pass the shared cache to the per-request dispatcher
            dispatcher = EventDispatcher(
                repo,
                logger=self.logger,
                rules_cache=self._rules_cache
            )
            # BUG 66 fix: record failures using a watchdog bound to the fresh repo
            watchdog = ApiWatchdog(repo)
        else:
            dispatcher = self.dispatcher  # type: ignore[assignment]  # already guarded above
            watchdog = self.watchdog

        # 2. Dispatch & Execute
        start_time = datetime.now(timezone.utc)
        dispatch_result = await dispatcher.dispatch(clean_text, msg.user)
        duration_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000

        result = dispatch_result.result if dispatch_result else None
        resolved_tool_id = dispatch_result.tool_id if dispatch_result else None

        # 3. Log Execution to DB (BUG 47/53: use resolved command_name if available)
        if result:
            logged_cmd = dispatch_result.command_name or clean_text.split(" ")[0][1:]
            await repo.log_execution(
                user_id=msg.user.id,
                platform=msg.platform,
                command_name=logged_cmd,
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
        # BUG 53 fix: use resolved_tool_id (from dispatch) — works for regex routes too
        # BUG 66 fix: use the isolated watchdog instance
        elif result and not result.ok:
            self.logger.error(f"Command failed: {result.error_reason}")
            if result.api_url and resolved_tool_id is not None:
                await watchdog.record_failure(
                    result.api_url, resolved_tool_id, result.error_reason or "unknown"
                )
            elif result.api_url:
                # Fallback: best-effort lookup by trigger text (exact routes only)
                cmd_name = clean_text.split(" ")[0][1:]
                tool = await repo.get_tool_by_command(cmd_name)
                if tool:
                    await watchdog.record_failure(
                        result.api_url, tool.id, result.error_reason or "unknown"
                    )
