"""
Normalization service: maps raw connector output to NormalizedSourceRecord.
Also builds short descriptions and normalizes fields.
"""

from __future__ import annotations

from src.schemas.source_record import NormalizedSourceRecord
from src.utils.hashing import compute_record_hash
from src.utils.text import truncate_text


def normalize_records(records: list[NormalizedSourceRecord]) -> list[NormalizedSourceRecord]:
    """
    Post-process records: compute hashes, clean up, ensure short_description.
    """
    normalized = []
    for record in records:
        record = _ensure_short_description(record)
        record = _compute_hash(record)
        normalized.append(record)
    return normalized


def _ensure_short_description(record: NormalizedSourceRecord) -> NormalizedSourceRecord:
    """Ensure short_description is populated."""
    if not record.short_description:
        if record.abstract_or_summary:
            record = record.model_copy(
                update={"short_description": truncate_text(record.abstract_or_summary, 200)}
            )
        elif record.title:
            record = record.model_copy(
                update={"short_description": truncate_text(record.title, 200)}
            )
    return record


def _compute_hash(record: NormalizedSourceRecord) -> NormalizedSourceRecord:
    """Compute normalized fingerprint hash for deduplication."""
    h = compute_record_hash(record)
    return record.model_copy(update={"normalized_hash": h})
