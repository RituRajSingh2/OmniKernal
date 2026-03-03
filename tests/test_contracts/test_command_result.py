"""Test stubs for CommandResult contract — factory methods."""
from src.core.contracts.command_result import CommandResult


def test_success_with_reply():
    result = CommandResult.success(reply="hello")
    assert result.ok is True
    assert result.reply == "hello"
    assert result.error_reason is None


def test_success_with_no_reply():
    result = CommandResult.success(reply=None)
    assert result.ok is True
    assert result.reply is None


def test_error_result():
    result = CommandResult.error(reason="API unreachable")
    assert result.ok is False
    assert result.reply is None
    assert result.error_reason == "API unreachable"


def test_success_repr():
    result = CommandResult.success(reply="hi")
    assert "ok=True" in repr(result)


def test_error_repr():
    result = CommandResult.error(reason="fail")
    assert "ok=False" in repr(result)
    assert "fail" in repr(result)
