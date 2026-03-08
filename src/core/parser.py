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

    # BUG 72: Cache for compiled regex objects to avoid re-compilation on every message
    _compiled_cache: dict[str, re.Pattern[str]] = {}

    @classmethod
    def match(cls, text: str, pattern: str) -> dict[str, str] | None:
        """
        Attempts to match text against a pattern.
        Returns a dict of extracted arguments on success, or None on failure.

        Conversion logic:
          1. Check cache for pre-compiled regex (BUG 72 fix).
          2. Split pattern on <arg_name> tokens, collecting literal segments.
          3. re.escape() each literal segment (BUG 41 fix).
          4. All placeholders except the last → "(?P<arg_name>.+?)" (BUG 7 fix).
          5. Compile and cache.
        """
        if not text or not pattern:
            return None

        # BUG 72 fix: Return from cache if we've seen this pattern before
        if pattern in cls._compiled_cache:
            match = cls._compiled_cache[pattern].match(text)
            return match.groupdict() if match else None

        # Split the pattern into alternating [literal, placeholder, literal, ...] parts
        parts = re.split(r"(<[^>]+>)", pattern)

        # Count placeholders
        placeholders = [p for p in parts if p.startswith("<") and p.endswith(">")]
        num_args = len(placeholders)

        if num_args == 0:
            # No arguments — literal match only
            try:
                # Cache literal matches too
                regex_pattern = f"^{re.escape(pattern)}$"
                compiled = re.compile(regex_pattern)
                cls._compiled_cache[pattern] = compiled
                return {} if compiled.match(text) else None
            except re.error:
                return None

        # Build regex by escaping literal parts and converting placeholders
        counter = 0
        regex_parts: list[str] = []

        for part in parts:
            if part.startswith("<") and part.endswith(">"):
                # Placeholder → named capture group
                counter += 1
                # BUG 130 + BUG 160 fix: sanitize group name. Must be alphanumeric/underscore
                # and cannot start with a digit.
                name = re.sub(r"\W", "_", part[1:-1])
                if name and name[0].isdigit():
                    name = f"_{name}"
                elif not name:
                    name = "arg"
                
                quantifier = ".+" if counter == num_args else ".+?"
                regex_parts.append(f"(?P<{name}>{quantifier})")
            else:
                # Literal segment → escape metacharacters (BUG 41 fix)
                regex_parts.append(re.escape(part))

        regex_string = f"^{''.join(regex_parts)}$"

        try:
            compiled = re.compile(regex_string)
            cls._compiled_cache[pattern] = compiled
            match = compiled.match(text)
            return match.groupdict() if match else None
        except re.error:
            return None
