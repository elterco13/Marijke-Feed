"""
Crossref connector — uses the Crossref REST API with cursor-based pagination.
https://api.crossref.org/swagger-ui/index.html
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.connectors.base import BaseConnector
from src.config.settings import Settings
from src.db.models import Profile
from src.schemas.source_record import NormalizedSourceRecord
from src.utils.dates import days_ago_date
from src.utils.text import clean_html, truncate_text

logger = logging.getLogger(__name__)

CROSSREF_BASE = "https://api.crossref.org"


class CrossrefConnector(BaseConnector):
    connector_key = "crossref"
    display_name = "Crossref"
    source_family = "academic"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.base_url = CROSSREF_BASE
        self.per_page = 20
        self.mailto = settings.contact_email

    def run(self, profile: Profile, query: str) -> list[NormalizedSourceRecord]:
        self.log_info(f"Starting search for profile '{profile.name}'")
        records: list[NormalizedSourceRecord] = []

        from_date = days_ago_date(profile.date_window_days)
        limit = profile.result_limit

        try:
            raw_results = self._fetch_works(query, from_date, limit)
        except Exception as e:
            self.log_error(f"Fetch failed: {e}")
            return records

        for item in raw_results:
            record = self._normalize(item)
            if record:
                records.append(record)

        self.log_info(f"Returned {len(records)} records.")
        return records

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"User-Agent": self.settings.user_agent}
        with httpx.Client(timeout=self.settings.request_timeout) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def _fetch_works(self, query: str, from_date: str, limit: int) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor = "*"
        fetched = 0

        # Convert YYYY-MM-DD to epoch seconds for Crossref
        try:
            from_dt = datetime.strptime(from_date, "%Y-%m-%d")
            from_epoch = int(from_dt.timestamp())
        except Exception:
            from_epoch = None

        while fetched < limit:
            per_page = min(self.per_page, limit - fetched)
            params: dict[str, Any] = {
                "query": query,
                "rows": per_page,
                "cursor": cursor,
                "sort": "published",
                "order": "desc",
                "mailto": self.mailto,
                "select": "DOI,title,abstract,author,published-print,published-online,container-title,type,URL,link,relation,subject,is-referenced-by-count",
            }
            if from_epoch:
                params["filter"] = f"from-pub-date:{from_date}"

            try:
                data = self._get(f"{self.base_url}/works", params)
            except Exception as e:
                self.log_error(f"Cursor page failed: {e}")
                break

            message = data.get("message", {})
            items = message.get("items", [])
            if not items:
                break

            results.extend(items)
            fetched += len(items)

            next_cursor = message.get("next-cursor")
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor

        return results[:limit]

    def _normalize(self, item: dict[str, Any]) -> NormalizedSourceRecord | None:
        try:
            titles = item.get("title", [])
            title = titles[0] if titles else ""
            if not title:
                return None

            doi = item.get("DOI")
            abstract = clean_html(item.get("abstract") or "")
            url = item.get("URL") or (f"https://doi.org/{doi}" if doi else None)

            # Published date
            pub_date = self._extract_date(item)

            # Journal
            container = item.get("container-title", [])
            journal = container[0] if container else None

            # Authors
            raw_authors = item.get("author", [])
            authors = []
            for a in raw_authors[:10]:
                given = a.get("given", "")
                family = a.get("family", "")
                full = f"{given} {family}".strip()
                if full:
                    authors.append(full)

            work_type = item.get("type", "journal-article")
            is_preprint = "preprint" in work_type.lower() or "posted-content" in work_type.lower()
            content_type = "preprint" if is_preprint else "article"

            return NormalizedSourceRecord(
                title=clean_html(title),
                abstract_or_summary=abstract or None,
                short_description=truncate_text(abstract, 200) if abstract else None,
                url=url,
                published_at=pub_date,
                journal_or_outlet=journal,
                authors=authors,
                doi=doi,
                external_id=doi,
                source_connector=self.connector_key,
                source_family=self.source_family,
                source_name=self.display_name,
                content_type=content_type,
                is_preprint=is_preprint,
                raw_payload=item,
            )
        except Exception as e:
            self.log_error(f"Normalization error: {e}")
            return None

    @staticmethod
    def _extract_date(item: dict[str, Any]) -> datetime | None:
        for key in ("published-print", "published-online", "created"):
            dp = item.get(key)
            if dp and "date-parts" in dp:
                parts = dp["date-parts"][0]
                try:
                    year = parts[0]
                    month = parts[1] if len(parts) > 1 else 1
                    day = parts[2] if len(parts) > 2 else 1
                    return datetime(year, month, day)
                except Exception:
                    continue
        return None
