"""
Core Logger ΓÇö Structured Contextual Logging

Wraps loguru to provide consistent, profile-aware logging across the core
and plugins. Supports both console and (in Phase 2) database logging.
"""

import sys
from loguru import logger

def setup_logger(level: str = "INFO", profile_name: str = "default"):
    """
    Configures loguru for OmniKernal.
    In Phase 1, we focus on console output with a clean format.
    """
    # Remove default handler
    logger.remove()

    # Add console handler with custom format
    # Example format: 2026-03-03 12:00:00 | INFO | [default] | Core booted
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

# Default global logger
core_logger = setup_logger()
