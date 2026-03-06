"""
Tests for OmniKernal Engine — unit and integration level.

BUG 15 fix: previous version imported non-existent MinimalLoader and
called CommandRouter() without the required repository argument, causing
the entire test module to crash on import. Rewritten to:
  - Use process() unit-test (no full boot needed)
  - Use proper AsyncMock for all dependencies
  - Use correct datetime.now(timezone.utc) for Message timestamps
"""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from src.core.engine import OmniKernal
from src.core.contracts.message import Message
from src.core.contracts.user import User
from src.core.contracts.command_result import CommandResult


def _make_msg(text: str = "!echo hello integration", user_id: str = "user1") -> Message:
    return Message(
        id="msg1",
        raw_text=text,
        user=User(id=user_id, display_name="Test User", platform="mock"),
        timestamp=datetime.now(timezone.utc),
        platform="mock"
    )


@pytest.mark.asyncio
async def test_engine_process_sends_reply():
    """
    Unit test: process() correctly routes a command and sends the reply
    via adapter.send_message() when CommandResult.reply is set.
    """
    mock_adapter = AsyncMock()
    mock_repo = AsyncMock()
    mock_repo.log_execution.return_value = None
    mock_repo.get_tool_by_command.return_value = None  # watchdog path not triggered

    engine = OmniKernal(mock_adapter, mock_repo)
    engine.is_running = True

    # Inject a pre-built dispatcher so we don't need a DB
    mock_dispatcher = AsyncMock()
    mock_dispatcher.dispatch.return_value = CommandResult.success(reply="Echo: hello integration")
    engine.dispatcher = mock_dispatcher

    await engine.process(_make_msg("!echo hello integration"))

    mock_adapter.send_message.assert_called_once_with("user1", "Echo: hello integration")


@pytest.mark.asyncio
async def test_engine_process_no_reply_skips_send():
    """
    Unit test: process() skips adapter.send_message() when reply is None.
    """
    mock_adapter = AsyncMock()
    mock_repo = AsyncMock()
    mock_repo.log_execution.return_value = None

    engine = OmniKernal(mock_adapter, mock_repo)
    engine.is_running = True

    mock_dispatcher = AsyncMock()
    mock_dispatcher.dispatch.return_value = CommandResult.success(reply=None)
    engine.dispatcher = mock_dispatcher

    await engine.process(_make_msg("!silent"))

    mock_adapter.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_engine_process_non_command_ignored():
    """
    Unit test: plain text (no '!' prefix) is silently ignored after sanitize.
    """
    mock_adapter = AsyncMock()
    mock_repo = AsyncMock()

    engine = OmniKernal(mock_adapter, mock_repo)
    engine.is_running = True
    engine.dispatcher = AsyncMock()

    await engine.process(_make_msg("hello world — not a command"))

    engine.dispatcher.dispatch.assert_not_called()
    mock_adapter.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_engine_process_before_init_returns_safely():
    """
    BUG 12 regression: process() called before dispatcher is initialised
    must return cleanly instead of raising AttributeError.
    """
    mock_adapter = AsyncMock()
    mock_repo = AsyncMock()

    engine = OmniKernal(mock_adapter, mock_repo)
    engine.is_running = True
    # dispatcher is None (default)

    # Must not raise
    await engine.process(_make_msg("!echo hi"))

    mock_adapter.send_message.assert_not_called()
