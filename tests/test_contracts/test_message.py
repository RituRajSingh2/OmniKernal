"""Test stubs for Message contract — construction and immutability."""
import pytest
from dataclasses import FrozenInstanceError
from datetime import datetime
from src.core.contracts.user import User
from src.core.contracts.message import Message


def _make_user() -> User:
    return User(id="u1", display_name="Alice", platform="whatsapp")


def test_message_construction():
    ts = datetime(2026, 3, 1, 12, 0, 0)
    msg = Message(id="m1", raw_text="!echo hello", user=_make_user(), timestamp=ts, platform="whatsapp")
    assert msg.id == "m1"
    assert msg.raw_text == "!echo hello"
    assert msg.platform == "whatsapp"
    assert msg.timestamp == ts


def test_message_is_immutable():
    ts = datetime(2026, 3, 1, 12, 0, 0)
    msg = Message(id="m2", raw_text="test", user=_make_user(), timestamp=ts, platform="whatsapp")
    with pytest.raises(FrozenInstanceError):
        msg.raw_text = "tampered"  # type: ignore[misc]


def test_message_repr_truncates_long_text():
    ts = datetime(2026, 3, 1, 12, 0, 0)
    long_text = "a" * 100
    msg = Message(id="m3", raw_text=long_text, user=_make_user(), timestamp=ts, platform="whatsapp")
    assert "..." in repr(msg)
