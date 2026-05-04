"""
URL normalization utilities.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse


def normalize_url(url: str | None) -> str:
    """Normalize URL: strip tracking params, lowercase scheme/host, remove trailing slash."""
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        normalized = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            parsed.params,
            "",  # strip query string for dedup
            "",  # strip fragment
        ))
        return normalized
    except Exception:
        return url.strip().lower().rstrip("/")
