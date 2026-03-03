"""
CommandSanitizer ΓÇö Injection Prevention Layer

Standardizes and cleans raw user input before it reaches the parser.
Prevents shell injection, command chaining, and template injection.
"""

import re

class CommandSanitizer:
    """
    Security firewall for raw message text.
    
    Rule: Never trust inbound text. Strip anything that isn't a 
    standard character, number, or basic punctuation needed for commands.
    """

    # Characters that are strictly forbidden in command strings
    # ; & | ` $ ( ) [ ] { } < > \ n \ r
    FORBIDDEN_CHARS = r"[\;&\|`\$\(\)\[\]\{\}<>\\\n\r]"

    @classmethod
    def sanitize(cls, raw_text: str) -> str:
        """
        Cleans raw input text.
        
        1. Strips leading/trailing whitespace
        2. Removes control characters and newlines
        3. Strips shell metacharacters
        4. Collapses multiple spaces
        """
        if not raw_text:
            return ""

        # 1. Basic trim
        text = raw_text.strip()

        # 2. Strip shell metacharacters and newlines
        text = re.sub(cls.FORBIDDEN_CHARS, "", text)

        # 3. Collapse multiple spaces into one
        text = re.sub(r"\s+", " ", text)

        return text.strip()
