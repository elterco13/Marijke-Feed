"""
Hashing utilities for record deduplication fingerprints.
"""

from __future__ import annotations

import hashlib
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.schemas.source_record import NormalizedSourceRecord


def compute_record_hash(record: "NormalizedSourceRecord") -> str:
    """
    Compute a stable hash for a record based on:
    - DOI (preferred)
    - URL
    - Normalized title + source_connector
    """
    if record.doi:
        key = f"doi:{_normalize_doi(record.doi)}"
    elif record.url:
        key = f"url:{record.url.strip().lower()}"
    else:
        title_norm = _normalize_text(record.title)
        key = f"title:{title_norm}:{record.source_connector}"

    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def _normalize_doi(doi: str) -> str:
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://doi\.org/", "", doi)
    return doi


def _normalize_text(text: str) -> str:
    t = text.lower().strip()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t
