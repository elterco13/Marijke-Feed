"""
Date utilities.
"""

from __future__ import annotations

from datetime import datetime, timedelta


def days_ago_date(days: int) -> str:
    """Return date string (YYYY-MM-DD) for N days ago."""
    dt = datetime.utcnow() - timedelta(days=days)
    return dt.strftime("%Y-%m-%d")


def date_to_str(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d")
