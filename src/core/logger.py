"""
Core Logger — Structured Contextual Logging

Wraps loguru to provide consistent, profile-aware logging across the core
and plugins. Supports both console and (in Phase 2) database logging.

BUG 38 fix: Added `logger.configure(extra={"profile": "system", "subsystem": "-"})`
to set safe defaults for ALL extra keys referenced in the format string.
Without this, any module that imports `from loguru import logger` directly
(e.g. encryption.py) and emits a log line would cause a KeyError on
`{extra[profile]}` because the raw logger has no bound extras.
"""

import sys
from typing import Any

from loguru import logger


def setup_logger(level: str = "INFO", profile_name: str = "default") -> Any:
    """
    Configures loguru for OmniKernal.
    In Phase 1, we focus on console output with a clean format.

    BUG 38 fix: Calls logger.configure(extra=...) to set safe fallback
    values before adding any handlers, so every log record has the keys
    that the format string references even if they weren't explicitly bound.
    """
    # BUG 38 fix: provide defaults for ALL extra keys used in the format string.
    # This prevents KeyError when raw `logger` (without .bind()) emits a record.
    logger.configure(extra={"profile": "system", "subsystem": "-"})

    # Remove default handler
    logger.remove()

    # Add console handler with custom format
    # Example: 2026-03-03 12:00:00 | INFO | [default] | watchdog | Core booted
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>[{extra[profile]}]</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(
        sys.stderr,
        format=log_format,
        level=level,
        colorize=True,
        enqueue=True  # Thread-safe / Async-safe
    )

    return logger.bind(profile=profile_name)


# Default global logger — has profile="default" bound
core_logger = setup_logger()
