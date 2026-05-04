"""
Generic RSS feed connector using feedparser.
Reads all enabled SavedSource records of type 'rss'.
"""

from __future__ import annotations

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser

from src.connectors.base import BaseConnector
from src.config.settings import Settings
from src.db.models import Profile, SavedSource
from src.db.session import get_session
from src.schemas.source_record import NormalizedSourceRecord
from src.utils.dates import days_ago_date
from src.utils.text import clean_html, truncate_text

logger = logging.getLogger(__name__)


class RSSConnector(BaseConnector):
    connector_key = "rss"
    display_name = "RSS Feeds"
    source_family = "rss"

    def __init__(self, settings: Settings):
        super().__init__(settings)

    def run(self, profile: Profile, query: str) -> list[NormalizedSourceRecord]:
        self.log_info(f"Starting RSS fetch for profile '{profile.name}'")
        records: list[NormalizedSourceRecord] = []

        from_date_str = days_ago_date(profile.date_window_days)
        from_dt = datetime.strptime(from_date_str, "%Y-%m-%d")

        feeds = self._load_enabled_feeds()
        if not feeds:
            self.log_info("No RSS feeds configured.")
            return records

        for feed in feeds:
            try:
                feed_records = self._parse_feed(feed, from_dt, profile.result_limit)
                records.extend(feed_records)
            except Exception as e:
                self.log_error(f"Feed '{feed.name}' failed: {e}")

        self.log_info(f"Returned {len(records)} records from {len(feeds)} feeds.")
        return records

    def _load_enabled_feeds(self) -> list[SavedSource]:
        with get_session() as session:
            return session.query(SavedSource).filter_by(is_enabled=True, source_type="rss").all()

    def _parse_feed(
        self, feed_source: SavedSource, from_dt: datetime, limit: int
    ) -> list[NormalizedSourceRecord]:
        records: list[NormalizedSourceRecord] = []

        feed_ua = feedparser.USER_AGENT
        feedparser.USER_AGENT = self.settings.user_agent

        try:
            parsed = feedparser.parse(feed_source.url)
        finally:
            feedparser.USER_AGENT = feed_ua

        if parsed.bozo and not parsed.entries:
            self.log_warning(f"Failed to parse feed: {feed_source.url} — {parsed.bozo_exception}")
            return records

        entries = parsed.entries[:limit]

        for entry in entries:
            record = self._normalize_entry(entry, feed_source, from_dt)
            if record:
                records.append(record)

        return records

    def _normalize_entry(
        self, entry: Any, source: SavedSource, from_dt: datetime
    ) -> NormalizedSourceRecord | None:
        try:
            title = clean_html(getattr(entry, "title", "") or "")
            if not title:
                return None

            # Parse date
            pub_date = self._parse_entry_date(entry)

            # Date filter
            if pub_date and pub_date < from_dt:
                return None

            summary = clean_html(getattr(entry, "summary", "") or "")
            url = getattr(entry, "link", None)
            external_id = getattr(entry, "id", None) or url

            # Try to get image from media content
            image_url = None
            media = getattr(entry, "media_content", [])
            if media and isinstance(media, list):
                for m in media:
                    if isinstance(m, dict) and m.get("medium") == "image":
                        image_url = m.get("url")
                        break
            if not image_url:
                # Try enclosures
                for enc in getattr(entry, "enclosures", []):
                    if hasattr(enc, "type") and "image" in enc.type:
                        image_url = enc.href
                        break

            # Authors
            authors = []
            author = getattr(entry, "author", None)
            if author:
                authors = [author]

            return NormalizedSourceRecord(
                title=title,
                abstract_or_summary=summary or None,
                short_description=truncate_text(summary, 200) if summary else None,
                url=url,
                image_url=image_url,
                published_at=pub_date,
                journal_or_outlet=source.name,
                authors=authors,
                external_id=external_id,
                source_connector=self.connector_key,
                source_family=self.source_family,
                source_name=source.name,
                content_type="rss",
                is_preprint=False,
                raw_payload={
                    "feed_name": source.name,
                    "feed_url": source.url,
                    "entry_id": external_id,
                },
            )
        except Exception as e:
            self.log_error(f"Entry normalization failed: {e}")
            return None

    @staticmethod
    def _parse_entry_date(entry: Any) -> datetime | None:
        """Try various date fields in feedparser entry."""
        # Try published_parsed or updated_parsed (struct_time)
        for attr in ("published_parsed", "updated_parsed", "created_parsed"):
            val = getattr(entry, attr, None)
            if val:
                try:
                    return datetime(*val[:6])
                except Exception:
                    pass

        # Try string fields
        for attr in ("published", "updated"):
            val = getattr(entry, attr, None)
            if val:
                try:
                    return parsedate_to_datetime(val).replace(tzinfo=None)
                except Exception:
                    pass

        return None
