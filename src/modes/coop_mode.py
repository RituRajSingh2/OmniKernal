"""
CoopMode — Human-in-the-Loop Execution Mode

Messages are held in a pending queue until a human explicitly approves
or rejects them. Only approved messages are routed through the Core pipeline.

This mode is designed for supervised operation where the operator wants
full control over what the bot responds to.
"""

import asyncio
from typing import TYPE_CHECKING, Optional
from src.core.logger import core_logger

if TYPE_CHECKING:
    from src.core.engine import OmniKernal
    from src.core.interfaces.platform_adapter import PlatformAdapter
    from src.core.contracts.message import Message


class CoopMode:
    """
    Human-in-the-loop execution mode.

    Polling loop: fetch_new_messages() → add to pending queue → wait for approval.
    Approval: approve(msg_id) releases message to core.process().
    Rejection: reject(msg_id) discards message with a log entry.
    """

    def __init__(self, poll_interval: float = 1.0):
        self.poll_interval = poll_interval
        self.logger = core_logger.bind(mode="coop")

        # Pending queue: msg_id -> Message
        self._pending: dict[str, "Message"] = {}
        # Approval signals: msg_id -> asyncio.Event
        self._approval_events: dict[str, asyncio.Event] = {}
        self._rejected: set[str] = set()

    @property
    def pending_messages(self) -> list["Message"]:
        """Returns a snapshot of all messages waiting for approval."""
        return list(self._pending.values())

    async def approve(self, msg_id: str) -> None:
        """
        Approves a pending message, releasing it to the Core pipeline.

        Args:
            msg_id: The message ID to approve.
        """
        if msg_id in self._approval_events:
            self.logger.info(f"Message approved: {msg_id}")
            self._approval_events[msg_id].set()
        else:
            self.logger.warning(f"approve() called for unknown msg_id: {msg_id}")

    async def reject(self, msg_id: str) -> None:
        """
        Rejects a pending message, discarding it without processing.

        Args:
            msg_id: The message ID to reject.
        """
        if msg_id in self._pending:
            self.logger.info(f"Message rejected: {msg_id}")
            self._rejected.add(msg_id)
            # Signal the event so the waiter unblocks and checks rejection
            if msg_id in self._approval_events:
                self._approval_events[msg_id].set()
        else:
            self.logger.warning(f"reject() called for unknown msg_id: {msg_id}")

    async def _hold_for_approval(self, msg: "Message") -> bool:
        """
        Holds a message in the pending queue until approved or rejected.

        Returns:
            True if approved, False if rejected.
        """
        msg_id = msg.id
        event = asyncio.Event()
        self._pending[msg_id] = msg
        self._approval_events[msg_id] = event

        self.logger.info(
            f"[COOP] Pending approval for msg '{msg_id}' from {msg.user.id}: "
            f"'{msg.raw_text}'"
        )

        await event.wait()

        # Cleanup
        approved = msg_id not in self._rejected
        self._pending.pop(msg_id, None)
        self._approval_events.pop(msg_id, None)
        self._rejected.discard(msg_id)

        return approved

    async def run(self, core: "OmniKernal", adapter: "PlatformAdapter") -> None:
        """
        The Co-op polling loop. Fetches messages and holds them for approval.

        Args:
            core: The OmniKernal engine instance.
            adapter: The connected PlatformAdapter.
        """
        self.logger.info(
            f"CoopMode started. Polling every {self.poll_interval}s. "
            "Awaiting human approval for each message."
        )

        while core.is_running:
            try:
                messages = await adapter.fetch_new_messages()

                for msg in messages:
                    # Don't await — let each message wait for approval concurrently
                    asyncio.create_task(self._process_with_approval(msg, core))

                await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                self.logger.info("CoopMode loop cancelled.")
                break
            except Exception as e:
                self.logger.warning(f"CoopMode error: {e}. Retrying in 2s.")
                await asyncio.sleep(2)

        self.logger.info("CoopMode stopped.")

    async def _process_with_approval(
        self, msg: "Message", core: "OmniKernal"
    ) -> None:
        """Internal: holds for approval then routes through Core."""
        approved = await self._hold_for_approval(msg)
        if approved:
            self.logger.info(f"Processing approved message: {msg.id}")
            await core.process(msg)
        else:
            self.logger.info(f"Skipped rejected message: {msg.id}")
