"""
Service to build search queries from Feed Builder ontology packs.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.db.models import Profile

DATA_DIR = Path(__file__).parent.parent.parent / "data"

def _load_json(filename: str) -> list[dict]:
    path = DATA_DIR / filename
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

# Lazy load ontology definitions
_CATEGORIES = []
_SUBCATEGORIES = []
_TAXON_PACKS = []
_EXCLUSION_PACKS = []

def _ensure_loaded():
    global _CATEGORIES, _SUBCATEGORIES, _TAXON_PACKS, _EXCLUSION_PACKS
    if not _CATEGORIES:
        _CATEGORIES = _load_json("categories.json")
    if not _SUBCATEGORIES:
        _SUBCATEGORIES = _load_json("subcategories.json")
    if not _TAXON_PACKS:
        _TAXON_PACKS = _load_json("taxon_packs.json")
    if not _EXCLUSION_PACKS:
        _EXCLUSION_PACKS = _load_json("exclusion_packs.json")

def get_all_categories() -> list[dict]:
    _ensure_loaded()
    return _CATEGORIES

def get_all_subcategories() -> list[dict]:
    _ensure_loaded()
    return _SUBCATEGORIES

def get_all_taxon_packs() -> list[dict]:
    _ensure_loaded()
    return _TAXON_PACKS

def get_all_exclusion_packs() -> list[dict]:
    _ensure_loaded()
    return _EXCLUSION_PACKS

def build_query(profile: Profile) -> str:
    """
    Compose a boolean search query string from the profile's selected packs and manual query text.
    Format is generally: (Taxa) AND (Categories OR Subcategories) NOT (Exclusions)
    """
    _ensure_loaded()
    
    # 1. Collect Taxa Keywords
    taxa_keywords = []
    selected_taxa_ids = profile.get_selected_taxon_packs()
    for pack in _TAXON_PACKS:
        if pack["id"] in selected_taxa_ids:
            taxa_keywords.extend(pack.get("keywords", []))
            
    # 2. Collect Category/Subcategory Keywords (Topic)
    topic_keywords = []
    selected_cat_ids = profile.get_selected_categories()
    for cat in _CATEGORIES:
        if cat["id"] in selected_cat_ids:
            topic_keywords.extend(cat.get("keywords", []))
            
    selected_subcat_ids = profile.get_selected_subcategories()
    for subcat in _SUBCATEGORIES:
        if subcat["id"] in selected_subcat_ids:
            topic_keywords.extend(subcat.get("keywords", []))

    # 3. Collect Exclusion Keywords
    exclusion_keywords = []
    selected_exc_ids = profile.get_selected_exclusions()
    for exc in _EXCLUSION_PACKS:
        if exc["id"] in selected_exc_ids:
            exclusion_keywords.extend(exc.get("keywords", []))

    # Build parts
    parts = []
    
    if taxa_keywords:
        parts.append("(" + " OR ".join(f'"{k}"' if " " in k else k for k in set(taxa_keywords)) + ")")
        
    if topic_keywords:
        parts.append("(" + " OR ".join(f'"{k}"' if " " in k else k for k in set(topic_keywords)) + ")")

    base_query = " AND ".join(parts)
    
    # Add manual query text if present
    if profile.query_text and profile.query_text.strip():
        if base_query:
            base_query = f"({base_query}) AND ({profile.query_text.strip()})"
        else:
            base_query = profile.query_text.strip()

    # Append exclusions
    if exclusion_keywords and base_query:
        # Note: NOT is supported by OpenAlex/Crossref/PubMed but syntax can vary slightly. 
        # Using standard 'NOT' works for most or is safely ignored.
        exclusions = " OR ".join(f'"{k}"' if " " in k else k for k in set(exclusion_keywords))
        base_query = f"{base_query} NOT ({exclusions})"
        
    return base_query
