"""
Rule-based relevance scoring engine.
Transparent, explainable scoring with JSON-config-driven rules.
Every component is recorded in the explanation dict.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.schemas.source_record import NormalizedSourceRecord

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"

# Score weight constants
TITLE_MULTIPLIER = 2.0  # title matches count double
ABSTRACT_MULTIPLIER = 1.0
JOURNAL_MULTIPLIER = 1.5
TAXON_SCORE = 5.0  # per taxon/species hit
POSITIVE_KW_SCORE = 3.0
NEGATIVE_KW_PENALTY = -5.0
HARD_EXCLUDE_SCORE = -999.0  # hard filter
PREPRINT_PENALTY = -2.0
DOI_TRUST_BONUS = 1.0
ABSTRACT_PRESENT_BONUS = 1.0
JOURNAL_BOOST_SCORE = 3.0


@dataclass
class ScoreExplanation:
    positive_title_hits: list[str] = field(default_factory=list)
    positive_abstract_hits: list[str] = field(default_factory=list)
    negative_hits: list[str] = field(default_factory=list)
    hard_excluded: bool = False
    hard_exclude_reason: str = ""
    taxon_hits: list[str] = field(default_factory=list)
    journal_boost: str = ""
    preprint_penalty: bool = False
    doi_bonus: bool = False
    abstract_bonus: bool = False
    category: str = ""
    subcategory: str = ""
    component_scores: dict[str, float] = field(default_factory=dict)
    total_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "positive_title_hits": self.positive_title_hits,
            "positive_abstract_hits": self.positive_abstract_hits,
            "negative_hits": self.negative_hits,
            "hard_excluded": self.hard_excluded,
            "hard_exclude_reason": self.hard_exclude_reason,
            "taxon_hits": self.taxon_hits,
            "journal_boost": self.journal_boost,
            "preprint_penalty": self.preprint_penalty,
            "doi_bonus": self.doi_bonus,
            "abstract_bonus": self.abstract_bonus,
            "category": self.category,
            "subcategory": self.subcategory,
            "component_scores": self.component_scores,
            "total_score": self.total_score,
        }


@lru_cache(maxsize=1)
def _load_include_keywords() -> list[dict]:
    path = _DATA_DIR / "include_keywords.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_exclude_keywords() -> list[dict]:
    path = _DATA_DIR / "exclude_keywords.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_source_boosts() -> dict[str, float]:
    path = _DATA_DIR / "source_boosts.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_category_rules() -> list[dict]:
    path = _DATA_DIR / "category_rules.json"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_taxa_data() -> dict:
    path = _DATA_DIR / "taxon_keywords.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def score_record(
    record: NormalizedSourceRecord,
    include_preprints: bool = True,
) -> NormalizedSourceRecord:
    """
    Score a single record and return updated record with score + explanation.
    """
    exp = ScoreExplanation()
    total = 0.0

    title_lower = record.title.lower() if record.title else ""
    abstract_lower = (record.abstract_or_summary or "").lower()
    journal_lower = (record.journal_or_outlet or "").lower()
    full_text_lower = f"{title_lower} {abstract_lower}"

    include_kws = _load_include_keywords()
    exclude_kws = _load_exclude_keywords()
    source_boosts = _load_source_boosts()
    taxa_data = _load_taxa_data()

    # --- Hard exclusion check ---
    for rule in exclude_kws:
        kw = rule.get("keyword", "").lower()
        hard = rule.get("hard_exclude", False)
        if not kw:
            continue
        if _kw_match(kw, title_lower) or _kw_match(kw, abstract_lower):
            if hard:
                exp.hard_excluded = True
                exp.hard_exclude_reason = kw
                exp.total_score = HARD_EXCLUDE_SCORE
                return record.model_copy(
                    update={
                        "relevance_score": HARD_EXCLUDE_SCORE,
                        "relevance_explanation": exp.to_dict(),
                    }
                )
            else:
                exp.negative_hits.append(kw)
                total += NEGATIVE_KW_PENALTY
                exp.component_scores[f"neg_kw:{kw}"] = NEGATIVE_KW_PENALTY

    # --- Positive keyword matching ---
    for rule in include_kws:
        kw = rule.get("keyword", "").lower()
        weight = rule.get("weight", 1.0)
        if not kw:
            continue
        in_title = _kw_match(kw, title_lower)
        in_abstract = _kw_match(kw, abstract_lower)

        if in_title:
            pts = POSITIVE_KW_SCORE * TITLE_MULTIPLIER * weight
            total += pts
            exp.positive_title_hits.append(kw)
            exp.component_scores[f"title_kw:{kw}"] = pts

        if in_abstract and not in_title:
            pts = POSITIVE_KW_SCORE * ABSTRACT_MULTIPLIER * weight
            total += pts
            exp.positive_abstract_hits.append(kw)
            exp.component_scores[f"abstract_kw:{kw}"] = pts

    # --- Taxon matching ---
    all_taxa = (
        taxa_data.get("genera", [])
        + taxa_data.get("families", [])
        + taxa_data.get("species", [])
        + list(taxa_data.get("common_names", {}).keys())
    )
    for taxon in all_taxa:
        if _kw_match(taxon.lower(), full_text_lower):
            pts = TAXON_SCORE
            if _kw_match(taxon.lower(), title_lower):
                pts *= TITLE_MULTIPLIER
            total += pts
            exp.taxon_hits.append(taxon)
            exp.component_scores[f"taxon:{taxon}"] = pts

    # --- Journal/source boost ---
    for journal_fragment, boost in source_boosts.items():
        if journal_fragment.lower() in journal_lower:
            total += boost
            exp.journal_boost = journal_fragment
            exp.component_scores[f"journal_boost:{journal_fragment}"] = boost
            break

    # --- Content type signals ---
    if record.is_preprint and not include_preprints:
        total += PREPRINT_PENALTY
        exp.preprint_penalty = True
        exp.component_scores["preprint_penalty"] = PREPRINT_PENALTY

    # --- Metadata completeness trust signals ---
    if record.doi:
        total += DOI_TRUST_BONUS
        exp.doi_bonus = True
        exp.component_scores["doi_bonus"] = DOI_TRUST_BONUS

    if record.abstract_or_summary:
        total += ABSTRACT_PRESENT_BONUS
        exp.abstract_bonus = True
        exp.component_scores["abstract_bonus"] = ABSTRACT_PRESENT_BONUS

    # --- Category assignment ---
    category, subcategory = _assign_category(record, title_lower, abstract_lower)
    exp.category = category
    exp.subcategory = subcategory

    exp.total_score = round(max(0.0, total), 2)

    return record.model_copy(
        update={
            "relevance_score": exp.total_score,
            "relevance_explanation": exp.to_dict(),
            "category": category or record.category,
            "subcategory": subcategory or record.subcategory,
        }
    )


def _assign_category(
    record: NormalizedSourceRecord,
    title_lower: str,
    abstract_lower: str,
) -> tuple[str, str]:
    """Assign category and subcategory based on category rules."""
    rules = _load_category_rules()
    full_text = f"{title_lower} {abstract_lower}"

    best_category = ""
    best_subcategory = ""
    best_score = 0

    for rule in rules:
        cat = rule.get("category", "")
        subcat = rule.get("subcategory", "")
        keywords = rule.get("keywords", [])

        matches = sum(1 for kw in keywords if _kw_match(kw.lower(), full_text))
        if matches > best_score:
            best_score = matches
            best_category = cat
            best_subcategory = subcat

    return best_category, best_subcategory


def score_records(
    records: list[NormalizedSourceRecord],
    include_preprints: bool = True,
) -> list[NormalizedSourceRecord]:
    """Score all records and sort by score descending."""
    scored = [score_record(r, include_preprints) for r in records]
    # Filter hard-excluded records
    scored = [r for r in scored if r.relevance_score > HARD_EXCLUDE_SCORE]
    scored.sort(key=lambda r: r.relevance_score, reverse=True)
    return scored


def _kw_match(keyword: str, text: str) -> bool:
    """Case-insensitive whole-word match."""
    if not keyword or not text:
        return False
    pattern = r"\b" + re.escape(keyword) + r"\b"
    return bool(re.search(pattern, text, re.IGNORECASE))
