"""
Taxonomy/species extraction service.
Dictionary-based matching from configurable JSON taxa lists.
Supports genus/species phrase matching and common names.
"""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


@lru_cache(maxsize=1)
def _load_taxa() -> dict:
    """Load taxon keywords from JSON file."""
    path = _DATA_DIR / "taxon_keywords.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extract_taxa(text: str) -> tuple[list[str], list[str]]:
    """
    Extract species mentions and higher taxa from text.
    Returns: (species_list, taxa_list)
    """
    if not text:
        return [], []

    taxa_data = _load_taxa()
    species_found: set[str] = set()
    taxa_found: set[str] = set()

    text_lower = text.lower()

    # Check genera and families
    for genus in taxa_data.get("genera", []):
        pattern = r"\b" + re.escape(genus.lower()) + r"\b"
        if re.search(pattern, text_lower):
            taxa_found.add(genus)

    # Check species (binomials)
    for species in taxa_data.get("species", []):
        pattern = r"\b" + re.escape(species.lower()) + r"\b"
        if re.search(pattern, text_lower):
            species_found.add(species)

    # Check common names -> map to scientific name
    for common, scientific in taxa_data.get("common_names", {}).items():
        pattern = r"\b" + re.escape(common.lower()) + r"\b"
        if re.search(pattern, text_lower):
            species_found.add(scientific)
            taxa_found.add(scientific.split()[0])  # genus part

    # Check families
    for family in taxa_data.get("families", []):
        pattern = r"\b" + re.escape(family.lower()) + r"\b"
        if re.search(pattern, text_lower):
            taxa_found.add(family)

    return sorted(species_found), sorted(taxa_found)
