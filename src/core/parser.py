"""
CommandParser ΓÇö Pattern Matching & Argument Extraction

Extends the Core's ability to understand "!command <arg>" patterns.
Uses regex generated from the declarative patterns in commands.yaml.
"""

import re
from typing import Any

class CommandParser:
    """
    Parses sanitized text against command patterns.
    
    Pattern syntax:
      "!echo <text>" -> matches "!echo hello world", args={"text": "hello world"}
      "!kick <user> <reason>" -> matches "!kick @rohit spam", args={"user": "@rohit", "reason": "spam"}
    """

    @classmethod
    def match(cls, text: str, pattern: str) -> dict[str, str] | None:
        """
        Attempts to match text against a pattern.
        Returns a dict of extracted arguments on success, or None on failure.
        
        Conversion logic:
          "<arg_name>" -> becomes a named regex group "(?P<arg_name>.+)"
        """
        if not text or not pattern:
            return None

        # 1. Escape the pattern for regex (except for the brackets)
        # We want to match exactly what's outside the <>, but allow anything inside.
        
        # Convert "<name>" to a named capturing group
        # This regex finds <something> and replaces it with (?P<something>.+)
        regex_pattern = re.sub(r"<([^>]+)>", r"(?P<\1>.+)", pattern)
        
        # Ensure we match from start to end, and escape spaces/other chars in original pattern
        # Note: This is an optimistic implementation; Phase 3 will handle complex escaping.
        try:
            # We use ^ and $ to ensure exact total match
            # But the prefix '!' is literal
            match = re.match(f"^{regex_pattern}$", text)
            if match:
                return match.groupdict()
        except re.error:
            # If the pattern itself is invalid regex (e.g. bad arg names)
            return None

        return None
