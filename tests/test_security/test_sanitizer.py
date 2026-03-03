import pytest
from src.security.sanitizer import CommandSanitizer

def test_sanitizer_basic():
    assert CommandSanitizer.sanitize("  !echo hello  ") == "!echo hello"

def test_sanitizer_injection_guards():
    # Shell characters
    assert CommandSanitizer.sanitize("!echo hello; rm -rf /") == "!echo hello rm -rf /"
    assert CommandSanitizer.sanitize("!echo `id`") == "!echo id"
    assert CommandSanitizer.sanitize("!echo $(whoami)") == "!echo whoami"
    
def test_sanitizer_newlines():
    assert CommandSanitizer.sanitize("!echo line1\n!echo line2") == "!echo line1!echo line2"

def test_sanitizer_multiple_spaces():
    assert CommandSanitizer.sanitize("!echo    too    many    spaces") == "!echo too many spaces"

def test_sanitizer_empty():
    assert CommandSanitizer.sanitize("") == ""
    assert CommandSanitizer.sanitize(None) == ""
