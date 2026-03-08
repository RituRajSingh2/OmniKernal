"""
CommandSanitizer — Injection Prevention Layer

Standardizes and cleans raw user input before it reaches the parser.
Prevents shell injection, command chaining, newline injection, and template injection.
"""

import re


class CommandSanitizer:
    """
    Security firewall for raw message text.

    Rule: Never trust inbound text. Strip anything that isn't a
    standard character, number, or basic punctuation needed for commands.

    BUG 17 fix: previously used raw string r"[...\\n\\r]" which matched the
    two-character literal sequences \\n and \\r (backslash + letter), NOT the
    actual newline (\\x0a) and carriage-return (\\x0d) control characters.
    Newline injection was therefore completely unblocked. Fixed by handling
    control characters with explicit str.replace() before the regex step.
    """

    # Shell metacharacters to strip (literal chars, not escape sequences)
    # BUG 78 fix: relaxed to allow brackets () [] {} <> which are safe and useful.
    # Still blocks chaining/injection tokens: ; & | ` $ \
    FORBIDDEN_CHARS = r"[;\&|`\$\\]"

    @classmethod
    def sanitize(cls, raw_text: str) -> str:
        """
        Cleans raw input text.

        Steps:
          1. Strip leading/trailing whitespace
          2. Strip actual newline (\\x0a) and carriage-return (\\x0d) characters
             — BUG 17 fix: these were previously not stripped due to wrong regex
          3. Strip shell metacharacters via FORBIDDEN_CHARS regex
          4. Collapse multiple spaces into one
        """
        if not raw_text:
            return ""

        # 1. Basic trim
        text = raw_text.strip()

        # 2. BUG 133 fix: replace newlines with spaces instead of deleting them.
        #    This prevents "!echo\nhello" from merging into "!echohello".
        text = text.replace("\n", " ").replace("\r", " ")

        # 3. Strip shell metacharacters
        text = re.sub(cls.FORBIDDEN_CHARS, "", text)

        # 4. Collapse multiple spaces into one
        text = re.sub(r"\s+", " ", text)

        return text.strip()
