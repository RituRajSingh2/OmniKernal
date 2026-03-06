"""
CommandParser — Pattern Matching & Argument Extraction

Extends the Core's ability to understand "!command <arg>" patterns.
Uses regex generated from the declarative patterns in commands.yaml.

BUG 7 fix: previously all placeholders used greedy `.+`, which caused the first
argument to consume the entire remaining string in multi-arg patterns.
Now all non-final args use non-greedy `.+?` and the final arg uses greedy `.+`.

BUG 41 fix: Previously, literal parts of patterns (everything outside <...>
placeholders) were left as raw regex. Patterns with metacharacters like `.`,
`(`, `)`, `+` etc. would produce incorrect regexes. Now each literal segment
between/around placeholders is passed through re.escape() before the final
regex is assembled. The change is backward-compatible: `!echo <text>` produces
the same match as before since `!echo ` contains no metacharacters.
"""

import re
from typing import Any, Optional


class CommandParser:
    """
    Parses sanitized text against command patterns.

    Pattern syntax:
      "!echo <text>"          → matches "!echo hello world", args={"text": "hello world"}
      "!kick <user> <reason>" → matches "!kick @rohit spam", args={"user": "@rohit", "reason": "spam"}

    Metacharacter safety (BUG 41):
      "!find . <path>"  → the literal "." is escaped, won't match any character
      "!add (n) <val>"  → literal parens are escaped, treated literally
    """

    @classmethod
    def match(cls, text: str, pattern: str) -> Optional[dict[str, str]]:
        """
        Attempts to match text against a pattern.
        Returns a dict of extracted arguments on success, or None on failure.

        Conversion logic:
          1. Split pattern on <arg_name> tokens, collecting literal segments
             and placeholder names in order.
          2. re.escape() each literal segment (BUG 41 fix).
          3. All placeholders except the last → "(?P<arg_name>.+?)" (BUG 7 fix)
          4. Last placeholder → "(?P<arg_name>.+)"
          5. Assemble and match.
        """
        if not text or not pattern:
            return None

        # Split the pattern into alternating [literal, placeholder, literal, ...] parts
        # re.split with a capturing group preserves the matched groups in the list
        parts = re.split(r"(<[^>]+>)", pattern)
        # parts = ["!echo ", "<text>", ""]  for "!echo <text>"
        # parts = ["!kick ", "<user>", " ", "<reason>", ""]  for "!kick <user> <reason>"

        # Count placeholders
        placeholders = [p for p in parts if p.startswith("<") and p.endswith(">")]
        num_args = len(placeholders)

        if num_args == 0:
            # No arguments — literal match only
            try:
                return {} if re.match(f"^{re.escape(pattern)}$", text) else None
            except re.error:
                return None

        # Build regex by escaping literal parts and converting placeholders
        # BUG 7 + BUG 41 fix
        counter = 0
        regex_parts: list[str] = []

        for part in parts:
            if part.startswith("<") and part.endswith(">"):
                # Placeholder → named capture group
                counter += 1
                name = part[1:-1]  # strip < >
                quantifier = ".+" if counter == num_args else ".+?"
                regex_parts.append(f"(?P<{name}>{quantifier})")
            else:
                # Literal segment → escape metacharacters (BUG 41 fix)
                regex_parts.append(re.escape(part))

        regex_pattern = "".join(regex_parts)

        try:
            match = re.match(f"^{regex_pattern}$", text)
            if match:
                return match.groupdict()
        except re.error:
            return None

        return None
