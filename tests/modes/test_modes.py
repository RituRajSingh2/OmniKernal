"""
Tests for Phase 6 — Execution Modes (SelfMode, CoopMode, ModeManager).
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from src.modes.self_mode import SelfMode
from src.modes.coop_mode import CoopMode
from src.modes.mode_manager import ModeManager
from src.core.contracts.message import Message
from src.core.contracts.user import User


def make_mock_msg(msg_id: str = "m1", text: str = "!echo hi") -> Message:
    return Message(
        id=msg_id,
        raw_text=text,
        user=User(id="user1", display_name="TestUser", platform="console", role="admin"),
        timestamp=datetime.now(),
        platform="console"
    )


def make_mock_core(messages: list[Message]) -> MagicMock:
    """Returns a mock core where is_running toggles off after messages are processed."""
    call_count = 0

    async def fake_fetch():
        nonlocal call_count
        if call_count == 0:
            call_count += 1
            return messages
        core.is_running = False
        return []

    core = MagicMock()
    core.is_running = True
    core.process = AsyncMock()
    adapter = MagicMock()
    adapter.fetch_new_messages = AsyncMock(side_effect=fake_fetch)
    return core, adapter


class TestSelfMode:
    """Self Mode: autonomous polling loop."""

    @pytest.mark.asyncio
    async def test_processes_all_messages(self):
        msgs = [make_mock_msg("m1", "!echo hello"), make_mock_msg("m2", "!echo world")]
        core, adapter = make_mock_core(msgs)

        mode = SelfMode(poll_interval=0.01)
        await mode.run(core, adapter)

        assert core.process.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_queue_no_process(self):
        core, adapter = make_mock_core([])
        mode = SelfMode(poll_interval=0.01)
        await mode.run(core, adapter)
        core.process.assert_not_called()


class TestCoopMode:
    """Co-op Mode: holds messages pending human approval."""

    @pytest.mark.asyncio
    async def test_approve_releases_to_pipeline(self):
        msg = make_mock_msg("m1", "!echo approved")
        core, adapter = make_mock_core([msg])

        mode = CoopMode(poll_interval=0.01)

        # Run coop mode in background
        task = asyncio.create_task(mode.run(core, adapter))
        await asyncio.sleep(0.05)  # let it poll

        # Approve while pending
        await mode.approve("m1")
        await asyncio.sleep(0.05)  # let approval process

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        core.process.assert_called_once_with(msg)

    @pytest.mark.asyncio
    async def test_reject_skips_pipeline(self):
        msg = make_mock_msg("m1", "!echo rejected")
        core, adapter = make_mock_core([msg])

        mode = CoopMode(poll_interval=0.01)

        task = asyncio.create_task(mode.run(core, adapter))
        await asyncio.sleep(0.05)

        await mode.reject("m1")
        await asyncio.sleep(0.05)

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

        core.process.assert_not_called()


class TestModeManager:
    """ModeManager: mode selection and lifecycle."""

    def test_builds_self_mode(self):
        mgr = ModeManager()
        mode = mgr._build_mode("self", 1.0)
        assert isinstance(mode, SelfMode)

    def test_builds_coop_mode(self):
        mgr = ModeManager()
        mode = mgr._build_mode("coop", 1.0)
        assert isinstance(mode, CoopMode)

    def test_unknown_mode_raises(self):
        mgr = ModeManager()
        with pytest.raises(ValueError, match="Unknown mode"):
            mgr._build_mode("turbo", 1.0)

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        core, adapter = make_mock_core([])

        mgr = ModeManager()
        await mgr.start("self", core, adapter, poll_interval=0.01)
        assert mgr.active_mode == "self"

        await mgr.stop()
        assert mgr.active_mode is None
