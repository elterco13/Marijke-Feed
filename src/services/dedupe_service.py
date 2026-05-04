"""
Deduplication service.

Priority order:
1. Exact DOI match
2. Normalized URL match
3. Exact normalized title match
4. Fuzzy title similarity + date proximity
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta

from rapidfuzz import fuzz

from src.schemas.source_record import NormalizedSourceRecord
from src.utils.text import normalize_title

logger = logging.getLogger(__name__)

FUZZY_TITLE_THRESHOLD = 88  # percent similarity
DATE_PROXIMITY_DAYS = 90  # days to consider titles close enough to be dupes


def deduplicate(records: list[NormalizedSourceRecord]) -> list[NormalizedSourceRecord]:
    """
    Deduplicate records and assign duplicate_group_key to grouped records.
    Returns only the best representative from each group.
    """
    if not records:
        return records

    groups: list[list[NormalizedSourceRecord]] = []
    assigned: set[int] = set()  # indices already assigned to a group

    # Step 1: DOI grouping
    doi_map: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        if rec.doi:
            key = _normalize_doi(rec.doi)
            doi_map.setdefault(key, []).append(i)

    for doi_key, indices in doi_map.items():
        if len(indices) > 1:
            group = [records[i] for i in indices]
            groups.append(group)
            assigned.update(indices)

    # Step 2: Normalized URL grouping (among unassigned)
    url_map: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        if i in assigned:
            continue
        if rec.url:
            key = _normalize_url(rec.url)
            url_map.setdefault(key, []).append(i)

    for url_key, indices in url_map.items():
        if len(indices) > 1:
            group = [records[i] for i in indices]
            groups.append(group)
            assigned.update(indices)

    # Step 3: Exact normalized title match (among unassigned)
    title_exact_map: dict[str, list[int]] = {}
    for i, rec in enumerate(records):
        if i in assigned:
            continue
        if rec.title:
            key = normalize_title(rec.title)
            title_exact_map.setdefault(key, []).append(i)

    for title_key, indices in title_exact_map.items():
        if len(indices) > 1:
            group = [records[i] for i in indices]
            groups.append(group)
            assigned.update(indices)

    # Step 4: Fuzzy title matching (among remaining unassigned)
    unassigned_indices = [i for i in range(len(records)) if i not in assigned]
    fuzzy_groups = _fuzzy_group(records, unassigned_indices)
    for group_indices in fuzzy_groups:
        group = [records[i] for i in group_indices]
        groups.append(group)
        assigned.update(group_indices)

    # Build output: keep best representative, tag all with group key
    output: list[NormalizedSourceRecord] = []

    for group in groups:
        best = _pick_best(group)
        group_key = best.normalized_hash or best.external_id or best.title[:20]
        # Tag all members
        for rec in group:
            rec = rec.model_copy(update={"duplicate_group_key": group_key})
        # Only emit the best
        output.append(best.model_copy(update={"duplicate_group_key": group_key}))

    # Add all singletons
    for i, rec in enumerate(records):
        if i not in assigned:
            output.append(rec)

    logger.info(
        f"Dedup: {len(records)} raw → {len(output)} after deduplication "
        f"({len(groups)} duplicate groups found)"
    )
    return output


def _fuzzy_group(
    records: list[NormalizedSourceRecord],
    indices: list[int],
) -> list[list[int]]:
    """Group records by fuzzy title similarity."""
    remaining = list(indices)
    groups: list[list[int]] = []

    while remaining:
        seed_idx = remaining.pop(0)
        seed = records[seed_idx]
        seed_title = normalize_title(seed.title)
        seed_date = seed.published_at

        group = [seed_idx]
        still_remaining = []

        for idx in remaining:
            cand = records[idx]
            cand_title = normalize_title(cand.title)
            score = fuzz.ratio(seed_title, cand_title)

            if score >= FUZZY_TITLE_THRESHOLD:
                # Check date proximity
                if seed_date and cand.published_at:
                    delta = abs((seed_date - cand.published_at).days)
                    if delta <= DATE_PROXIMITY_DAYS:
                        group.append(idx)
                        continue
                elif score >= 95:
                    # Very high similarity, allow even without date
                    group.append(idx)
                    continue

            still_remaining.append(idx)

        remaining = still_remaining

        if len(group) > 1:
            groups.append(group)
        # Singletons go back to unassigned (handled by caller)

    return groups


def _pick_best(group: list[NormalizedSourceRecord]) -> NormalizedSourceRecord:
    """Pick the best representative from a duplicate group."""
    # Preference: has DOI > has abstract > published record over preprint > most recent
    def score(r: NormalizedSourceRecord) -> tuple:
        return (
            1 if r.doi else 0,
            1 if r.abstract_or_summary else 0,
            0 if r.is_preprint else 1,
            r.published_at.timestamp() if r.published_at else 0,
        )

    return max(group, key=score)


def _normalize_doi(doi: str) -> str:
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://doi\.org/", "", doi)
    return doi


def _normalize_url(url: str) -> str:
    url = url.strip().lower()
    url = re.sub(r"https?://", "", url)
    url = url.rstrip("/")
    return url
