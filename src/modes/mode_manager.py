"""
ModeManager — Execution Mode Lifecycle Controller

Selects, starts, and stops execution modes (SelfMode / CoopMode).
Acts as the single point of control for switching how the Core drives messages.
"""

import asyncio
import contextlib
from typing import TYPE_CHECKING, Literal

from src.core.logger import core_logger
from src.modes.coop_mode import CoopMode
from src.modes.self_mode import SelfMode

if TYPE_CHECKING:
    from src.core.engine import OmniKernal
    from src.core.interfaces.platform_adapter import PlatformAdapter

ModeName = Literal["self", "coop"]


class ModeManager:
    """
    Manages execution mode selection and lifecycle.

    Usage:
        manager = ModeManager()
        await manager.start("self", core, adapter)
        # ...later...
        await manager.stop()
    """

    def __init__(self) -> None:
        self._active_mode_name: ModeName | None = None
        self._active_mode: SelfMode | CoopMode | None = None
        self._task: asyncio.Task[None] | None = None
        self.logger = core_logger.bind(subsystem="mode_manager")

    @property
    def active_mode(self) -> ModeName | None:
        """Returns the name of the currently active mode."""
        return self._active_mode_name

    def _build_mode(self, mode_name: ModeName, poll_interval: float) -> SelfMode | CoopMode:
        """Instantiates the correct mode object by name."""
        if mode_name == "self":
            return SelfMode(poll_interval=poll_interval)
        elif mode_name == "coop":
            return CoopMode(poll_interval=poll_interval)
        else:
            raise ValueError(f"Unknown mode: '{mode_name}'. Must be 'self' or 'coop'.")

    async def start(
        self,
        mode_name: ModeName,
        core: "OmniKernal",
        adapter: "PlatformAdapter",
        poll_interval: float = 1.0,
    ) -> None:
        """
        Starts the specified execution mode as a background asyncio task.

        Args:
            mode_name: "self" or "coop".
            core: The OmniKernal engine instance.
            adapter: The connected PlatformAdapter.
            poll_interval: Seconds between polls.
        """
        if self._task and not self._task.done():
            self.logger.warning(
                f"ModeManager: stopping existing mode '{self._active_mode_name}' "
                f"before starting '{mode_name}'."
            )
            await self.stop()

        self._active_mode = self._build_mode(mode_name, poll_interval)
        self._active_mode_name = mode_name
        self._task = asyncio.create_task(
            self._active_mode.run(core, adapter),
            name=f"mode_{mode_name}",
        )

        self.logger.info(f"ModeManager: started mode '{mode_name}'.")

    async def stop(self) -> None:
        """Gracefully stops the active execution mode."""
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

        self._task = None
        self._active_mode = None
        self._active_mode_name = None
        self.logger.info("ModeManager: stopped.")

    def get_mode_instance(self) -> SelfMode | CoopMode | None:
        """Returns the active mode instance (for co-op approve/reject access)."""
        return self._active_mode
