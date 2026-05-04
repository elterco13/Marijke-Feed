"""
OpenAlex connector — searches the OpenAlex academic literature API.
https://docs.openalex.org/
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
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

OPENALEX_BASE = "https://api.openalex.org"


class OpenAlexConnector(BaseConnector):
    connector_key = "openalex"
    display_name = "OpenAlex"
    source_family = "academic"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.base_url = OPENALEX_BASE
        self.per_page = 25
        self.mailto = settings.openalex_email

    def run(self, profile: Profile, query: str) -> list[NormalizedSourceRecord]:
        self.log_info(f"Starting search for profile '{profile.name}' query='{query}'")
        records: list[NormalizedSourceRecord] = []

        from_date = days_ago_date(profile.date_window_days)
        limit = profile.result_limit

        try:
            raw_results = self._fetch_works(
                query=query,
                from_date=from_date,
                limit=limit,
                include_preprints=profile.include_preprints,
            )
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
    def _fetch_page(self, params: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "application/json",
        }
        with httpx.Client(timeout=self.settings.request_timeout) as client:
            resp = client.get(f"{self.base_url}/works", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def _fetch_works(
        self,
        query: str,
        from_date: str,
        limit: int,
        include_preprints: bool,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        page = 1
        fetched = 0

        # Build filter
        filters = [f"from_publication_date:{from_date}"]
        if not include_preprints:
            filters.append("is_preprint:false")

        while fetched < limit:
            per_page = min(self.per_page, limit - fetched)
            params: dict[str, Any] = {
                "search": query,
                "filter": ",".join(filters),
                "sort": "publication_date:desc",
                "per-page": per_page,
                "page": page,
                "mailto": self.mailto,
                "select": "id,title,abstract_inverted_index,doi,publication_date,type,primary_location,locations,authorships,ids,is_oa,open_access,cited_by_count,language",
            }

            try:
                data = self._fetch_page(params)
            except Exception as e:
                self.log_error(f"Page {page} failed: {e}")
                break

            items = data.get("results", [])
            if not items:
                break

            results.extend(items)
            fetched += len(items)

            meta = data.get("meta", {})
            total = meta.get("count", 0)
            if fetched >= total:
                break

            page += 1

        return results[:limit]

    def _normalize(self, item: dict[str, Any]) -> NormalizedSourceRecord | None:
        try:
            title = item.get("title") or ""
            if not title:
                return None

            # Reconstruct abstract from inverted index
            abstract = self._reconstruct_abstract(item.get("abstract_inverted_index"))

            doi = None
            doi_raw = item.get("doi")
            if doi_raw:
                doi = doi_raw.replace("https://doi.org/", "").strip()

            # Publication date
            pub_date_str = item.get("publication_date")
            pub_date = None
            if pub_date_str:
                try:
                    pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
                except ValueError:
                    pass

            # Primary location for journal/URL
            primary_loc = item.get("primary_location") or {}
            source = primary_loc.get("source") or {}
            journal = source.get("display_name")
            landing_url = primary_loc.get("landing_page_url") or item.get("id")

            # Authors
            authorships = item.get("authorships") or []
            authors = []
            for auth in authorships[:10]:
                author_obj = auth.get("author") or {}
                name = author_obj.get("display_name")
                if name:
                    authors.append(name)

            # Content type
            work_type = item.get("type", "article")
            is_preprint = work_type in ("preprint",) or "preprint" in (item.get("type_crossref") or "").lower()
            content_type = "preprint" if is_preprint else "article"

            external_id = item.get("id", "")

            return NormalizedSourceRecord(
                title=clean_html(title),
                abstract_or_summary=clean_html(abstract) if abstract else None,
                short_description=truncate_text(clean_html(abstract) if abstract else "", 200),
                url=landing_url,
                published_at=pub_date,
                journal_or_outlet=journal,
                authors=authors,
                doi=doi,
                external_id=external_id,
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
    def _reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
        """Reconstruct abstract text from OpenAlex inverted index."""
        if not inverted_index:
            return None
        try:
            index: dict[int, str] = {}
            for word, positions in inverted_index.items():
                for pos in positions:
                    index[pos] = word
            return " ".join(index[i] for i in sorted(index.keys()))
        except Exception:
            return None
