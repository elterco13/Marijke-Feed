"""
Text processing utilities.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def clean_html(text: str | None) -> str:
    """Strip HTML tags and clean whitespace."""
    if not text:
        return ""
    try:
        soup = BeautifulSoup(text, "lxml")
        cleaned = soup.get_text(separator=" ")
    except Exception:
        cleaned = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def truncate_text(text: str | None, max_chars: int = 200) -> str:
    """Truncate text to max_chars, ending at a word boundary."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars * 0.7:
        truncated = truncated[:last_space]
    return truncated.rstrip(".,;:") + "…"


def normalize_title(title: str) -> str:
    """Normalize title for comparison: lowercase, strip punctuation/whitespace."""
    t = title.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t
