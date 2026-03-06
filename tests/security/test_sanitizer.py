"""
CommandSanitizer Tests — consolidated (BUG 18 fix)

Merged unique cases from the now-deleted tests/test_security/test_sanitizer.py
into this canonical location.
"""

import pytest
from src.security.sanitizer import CommandSanitizer


def test_command_sanitization_basics():
    # Trim
    assert CommandSanitizer.sanitize("  hello  ") == "hello"

    # Collapse spaces
    assert CommandSanitizer.sanitize("cmd   arg1   arg2") == "cmd arg1 arg2"


def test_sanitizer_basic_prefix():
    """Merged from tests/test_security/test_sanitizer.py"""
    assert CommandSanitizer.sanitize("  !echo hello  ") == "!echo hello"


def test_command_injection_prevention():
    payloads = [
        # Command chaining
        ("!echo hello; rm -rf /", "!echo hello rm -rf /"),
        ("!echo hello && cat /etc/passwd", "!echo hello cat /etc/passwd"),
        ("!echo a | grep", "!echo a grep"),

        # Shell substitution
        ("!echo `ls`", "!echo ls"),
        ("!echo $(whoami)", "!echo whoami"),

        # Newline injection
        ("!echo hello\n!admin_cmd", "!echo hello!admin_cmd"),
        ("!cmd\r\n!next", "!cmd!next"),

        # Template injection
        ("!say {config.api_key}", "!say config.api_key"),
        ("!test <script>alert(1)</script>", "!test scriptalert1/script"),

        # Redirection
        ("!echo foo > /tmp/bad", "!echo foo /tmp/bad"),
    ]

    for payload, expected in payloads:
        assert CommandSanitizer.sanitize(payload) == expected


def test_sanitizer_empty():
    """Merged from tests/test_security/test_sanitizer.py"""
    assert CommandSanitizer.sanitize("") == ""
    assert CommandSanitizer.sanitize(None) == ""
