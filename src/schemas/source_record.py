"""
Normalized source record schema — common output for all connectors.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class NormalizedSourceRecord(BaseModel):
    """The canonical output schema for all connectors."""

    title: str = ""
    abstract_or_summary: Optional[str] = None
    short_description: Optional[str] = None

    url: Optional[str] = None
    image_url: Optional[str] = None
    published_at: Optional[datetime] = None

    journal_or_outlet: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    doi: Optional[str] = None
    external_id: Optional[str] = None

    source_connector: str = ""
    source_family: str = ""
    source_name: Optional[str] = None

    content_type: Optional[str] = None  # article, preprint, news, rss, communication
    is_preprint: bool = False

    category: Optional[str] = None
    subcategory: Optional[str] = None
    species: list[str] = Field(default_factory=list)
    taxa: list[str] = Field(default_factory=list)

    raw_payload: Optional[dict[str, Any]] = None
    relevance_score: float = 0.0
    relevance_explanation: dict[str, Any] = Field(default_factory=dict)

    # Internal dedup fields
    normalized_hash: Optional[str] = None
    duplicate_group_key: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True

    def get_text_for_scoring(self) -> str:
        """Return concatenated text for relevance scoring."""
        parts = [self.title or ""]
        if self.abstract_or_summary:
            parts.append(self.abstract_or_summary)
        if self.journal_or_outlet:
            parts.append(self.journal_or_outlet)
        return " ".join(parts)

    def get_title_text(self) -> str:
        return self.title or ""

    def get_abstract_text(self) -> str:
        return self.abstract_or_summary or ""
