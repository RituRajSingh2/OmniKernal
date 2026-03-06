"""
CommandParser — Pattern Matching & Argument Extraction

Extends the Core's ability to understand "!command <arg>" patterns.
Uses regex generated from the declarative patterns in commands.yaml.
"""

import re
from typing import Any, Optional


class CommandParser:
    """
    Parses sanitized text against command patterns.

    Pattern syntax:
      "!echo <text>"          → matches "!echo hello world", args={"text": "hello world"}
      "!kick <user> <reason>" → matches "!kick @rohit spam", args={"user": "@rohit", "reason": "spam"}

    BUG 7 fix: previously all placeholders used greedy `.+`, which caused the first
    argument to consume the entire remaining string in multi-arg patterns.
    Now all non-final args use non-greedy `.+?` and the final arg uses greedy `.+`.
    """

    @classmethod
    def match(cls, text: str, pattern: str) -> Optional[dict[str, str]]:
        """
        Attempts to match text against a pattern.
        Returns a dict of extracted arguments on success, or None on failure.

        Conversion logic:
          - All placeholders except the last: "<arg_name>" → "(?P<arg_name>.+?)"
          - Last placeholder: "<arg_name>" → "(?P<arg_name>.+)"
        """
        if not text or not pattern:
            return None

        # Find all argument names in declaration order
        arg_names = re.findall(r"<([^>]+)>", pattern)
        num_args = len(arg_names)

        if num_args == 0:
            # No arguments — do a literal match
            try:
                escaped = re.escape(pattern)
                return {} if re.match(f"^{escaped}$", text) else None
            except re.error:
                return None

        # BUG 7 fix: build regex with non-greedy for all non-final args
        # This allows "!kick <user> <reason>" to correctly split "!kick @rohit spam"
        # into {"user": "@rohit", "reason": "spam"} instead of {"user": "@rohit spam", "reason": ""}
        counter = 0

        def replace_arg(m: re.Match) -> str:
            nonlocal counter
            counter += 1
            name = m.group(1)
            # Use non-greedy for all args except the last
            quantifier = ".+" if counter == num_args else ".+?"
            return f"(?P<{name}>{quantifier})"

        regex_pattern = re.sub(r"<([^>]+)>", replace_arg, pattern)

        try:
            match = re.match(f"^{regex_pattern}$", text)
            if match:
                return match.groupdict()
        except re.error:
            return None

        return None
