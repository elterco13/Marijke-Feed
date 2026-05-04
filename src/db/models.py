"""
SQLAlchemy ORM models for Aquarium Science Monitor.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


def _now() -> datetime:
    return datetime.utcnow()


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    query_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_window_days: Mapped[int] = mapped_column(Integer, default=30)
    result_limit: Mapped[int] = mapped_column(Integer, default=50)
    include_preprints: Mapped[bool] = mapped_column(Boolean, default=True)

    source_types_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled_connectors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Feed Builder Selections
    selected_categories_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_subcategories_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_taxon_packs_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    selected_exclusions_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    include_keywords_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    exclude_keywords_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    taxon_allowlist_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    taxon_blocklist_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    journals_allowlist_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    journals_blocklist_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    runs: Mapped[list["SearchRun"]] = relationship("SearchRun", back_populates="profile")

    def get_enabled_connectors(self) -> list[str]:
        if self.enabled_connectors_json:
            return json.loads(self.enabled_connectors_json)
        return []

    def get_selected_categories(self) -> list[str]:
        if self.selected_categories_json:
            return json.loads(self.selected_categories_json)
        return []

    def get_selected_subcategories(self) -> list[str]:
        if self.selected_subcategories_json:
            return json.loads(self.selected_subcategories_json)
        return []

    def get_selected_taxon_packs(self) -> list[str]:
        if self.selected_taxon_packs_json:
            return json.loads(self.selected_taxon_packs_json)
        return []

    def get_selected_exclusions(self) -> list[str]:
        if self.selected_exclusions_json:
            return json.loads(self.selected_exclusions_json)
        return []

    def get_include_keywords(self) -> list[str]:
        if self.include_keywords_json:
            return json.loads(self.include_keywords_json)
        return []

    def get_exclude_keywords(self) -> list[str]:
        if self.exclude_keywords_json:
            return json.loads(self.exclude_keywords_json)
        return []

    def get_manual_taxa(self) -> list[str]:
        if self.taxon_allowlist_json:
            return json.loads(self.taxon_allowlist_json)
        return []

    def get_manual_categories(self) -> list[str]:
        if self.include_keywords_json:
            return json.loads(self.include_keywords_json)
        return []


class Connector(Base):
    __tablename__ = "connectors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_family: Mapped[str] = mapped_column(String(100), nullable=False)
    enabled_by_default: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    def get_config(self) -> dict[str, Any]:
        if self.config_json:
            return json.loads(self.config_json)
        return {}


class SearchRun(Base):
    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[int] = mapped_column(Integer, ForeignKey("profiles.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, running, done, error
    total_raw_results: Mapped[int] = mapped_column(Integer, default=0)
    total_normalized_results: Mapped[int] = mapped_column(Integer, default=0)
    total_deduped_results: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    profile: Mapped["Profile"] = relationship("Profile", back_populates="runs")
    results: Mapped[list["Result"]] = relationship("Result", back_populates="run")


class Result(Base):
    __tablename__ = "results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("search_runs.id"), nullable=False)
    profile_id: Mapped[int] = mapped_column(Integer, nullable=False)

    source_connector: Mapped[str] = mapped_column(String(100), nullable=False)
    source_family: Mapped[str] = mapped_column(String(100), nullable=False)
    source_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    external_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract_or_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    short_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    journal_or_outlet: Mapped[str | None] = mapped_column(String(500), nullable=True)
    authors_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    subcategory: Mapped[str | None] = mapped_column(String(255), nullable=True)
    species_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    taxa_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_preprint: Mapped[bool] = mapped_column(Boolean, default=False)

    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_explanation_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    raw_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    duplicate_group_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    is_irrelevant: Mapped[bool] = mapped_column(Boolean, default=False)
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    run: Mapped["SearchRun"] = relationship("SearchRun", back_populates="results")

    def get_authors(self) -> list[str]:
        if self.authors_json:
            return json.loads(self.authors_json)
        return []

    def get_species(self) -> list[str]:
        if self.species_json:
            return json.loads(self.species_json)
        return []

    def get_taxa(self) -> list[str]:
        if self.taxa_json:
            return json.loads(self.taxa_json)
        return []

    def get_relevance_explanation(self) -> dict[str, Any]:
        if self.relevance_explanation_json:
            return json.loads(self.relevance_explanation_json)
        return {}


class SavedSource(Base):
    """User-managed RSS feeds and custom sources."""
    __tablename__ = "saved_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(100), default="rss")  # rss, api, news
    source_family: Mapped[str] = mapped_column(String(100), default="rss")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class NegativeFeedbackRule(Base):
    """Lightweight exclusion rules for the relevance engine."""
    __tablename__ = "negative_feedback_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_type: Mapped[str] = mapped_column(String(100), nullable=False)  # keyword, journal, taxon, source, pattern
    rule_value: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
