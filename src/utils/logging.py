"""
Logging setup for Aquarium Science Monitor.
"""

from __future__ import annotations

import logging
import sys
from src.config.settings import get_settings


def setup_logging() -> None:
    """Configure application-wide logging."""
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Reduce noise from third-party libraries
    for lib in ("httpx", "httpcore", "feedparser", "urllib3"):
        logging.getLogger(lib).setLevel(logging.WARNING)
