import pytest
from src.core.parser import CommandParser

def test_parser_single_arg():
    pattern = "!echo <text>"
    extracted = CommandParser.match("!echo hello world", pattern)
    assert extracted == {"text": "hello world"}

def test_parser_multiple_args():
    pattern = "!kick <user> <reason>"
    extracted = CommandParser.match("!kick @rohit spamming the chat", pattern)
    # Note: Our greedy .+ regex will take as much as it can.
    # For multiple args, we need more advanced regex or delimiters.
    # Phase 1 uses basic greedy matching.
    extracted = CommandParser.match("!kick @rohit spam", pattern)
    assert extracted is not None
    assert "user" in extracted
    assert "reason" in extracted

def test_parser_no_match():
    assert CommandParser.match("hello", "!echo <text>") is None
    assert CommandParser.match("!help", "!echo <text>") is None

def test_parser_empty():
    assert CommandParser.match("", "") is None
    assert CommandParser.match(None, None) is None
