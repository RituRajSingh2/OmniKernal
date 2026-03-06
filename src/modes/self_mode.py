"""
SelfMode — Autonomous Execution Mode

Fully autonomous polling loop. The bot reads new messages from the adapter
and routes them through the Core pipeline without any human intervention.

This is the default execution mode for OmniKernal.

BUG 40 fix: The exception handler in the polling loop now distinguishes
between recoverable errors (network glitches, transient failures) and
critical errors that should stop the engine. BaseException subclasses
that are not Exception (e.g. SystemExit, KeyboardInterrupt) are not caught
and propagate naturally. asyncio.CancelledError is handled explicitly.
"""

import asyncio
from typing import TYPE_CHECKING
from src.core.logger import core_logger

if TYPE_CHECKING:
    from src.core.engine import OmniKernal
    from src.core.interfaces.platform_adapter import PlatformAdapter


class SelfMode:
    """
    Autonomous execution mode.

    The Core polls the adapter on a fixed interval, processes every
    incoming message, and sends replies — no human involvement.

    Loop: fetch_new_messages() → process() → send_message()
    """

    def __init__(self, poll_interval: float = 1.0):
        self.poll_interval = poll_interval
        self.logger = core_logger.bind(mode="self")

    async def run(self, core: "OmniKernal", adapter: "PlatformAdapter") -> None:
        """
        The main autonomous polling loop.

        Args:
            core: The OmniKernal engine instance.
            adapter: The connected PlatformAdapter.
        """
        self.logger.info(
            f"SelfMode started. Polling every {self.poll_interval}s."
        )

        while core.is_running:
            try:
                messages = await adapter.fetch_new_messages()

                for msg in messages:
                    await core.process(msg)

                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                self.logger.info("SelfMode loop cancelled.")
                break
            except Exception as e:
                # BUG 40 fix: Only retry on genuinely transient errors.
                # Classify the exception before deciding to swallow it.
                error_type = type(e).__name__
                is_likely_fatal = isinstance(
                    e, (MemoryError, RuntimeError, PermissionError, OSError)
                ) and not isinstance(e, (ConnectionError, TimeoutError))

                if is_likely_fatal:
                    self.logger.error(
                        f"SelfMode: fatal error ({error_type}): {e}. Stopping loop."
                    )
                    # Stop the engine rather than silently retry forever
                    if core.is_running:
                        asyncio.create_task(core.stop())
                    break
                else:
                    self.logger.warning(
                        f"SelfMode: transient error ({error_type}): {e}. Retrying in 2s."
                    )
                    await asyncio.sleep(2)

        self.logger.info("SelfMode stopped.")
