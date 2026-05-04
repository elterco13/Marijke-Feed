"""
Europe PMC connector.
https://europepmc.org/RestfulWebService
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

EPMC_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"


class EuropePMCConnector(BaseConnector):
    connector_key = "europepmc"
    display_name = "Europe PMC"
    source_family = "academic"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.base_url = EPMC_BASE
        self.per_page = 25

    def run(self, profile: Profile, query: str) -> list[NormalizedSourceRecord]:
        self.log_info(f"Starting search for profile '{profile.name}'")
        records: list[NormalizedSourceRecord] = []

        from_date = days_ago_date(profile.date_window_days)
        limit = profile.result_limit

        try:
            raw_results = self._fetch_articles(
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
    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        headers = {"User-Agent": self.settings.user_agent}
        with httpx.Client(timeout=self.settings.request_timeout) as client:
            resp = client.get(f"{self.base_url}/search", params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()

    def _fetch_articles(
        self,
        query: str,
        from_date: str,
        limit: int,
        include_preprints: bool,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor_mark = "*"
        fetched = 0

        # Build query with date filter
        date_filter = f"FIRST_PDATE:[{from_date} TO *]"
        source_filter = ""
        if not include_preprints:
            source_filter = " AND SRC:MED OR SRC:PMC OR SRC:AGR OR SRC:CBA OR SRC:CTX OR SRC:ETH OR SRC:HIR OR SRC:MED OR SRC:PAT OR SRC:PPR:N"
        
        full_query = f"({query}) AND {date_filter}"
        if not include_preprints:
            full_query += " NOT (SRC:PPR)"

        while fetched < limit:
            per_page = min(self.per_page, limit - fetched)
            params: dict[str, Any] = {
                "query": full_query,
                "resultType": "core",
                "pageSize": per_page,
                "cursorMark": cursor_mark,
                "sort": "P_PDATE_D desc",
                "format": "json",
            }

            try:
                data = self._get(params)
            except Exception as e:
                self.log_error(f"Page failed: {e}")
                break

            result_list = data.get("resultList", {})
            items = result_list.get("result", [])
            if not items:
                break

            results.extend(items)
            fetched += len(items)

            next_cursor = data.get("nextCursorMark")
            if not next_cursor or next_cursor == cursor_mark:
                break
            cursor_mark = next_cursor

        return results[:limit]

    def _normalize(self, item: dict[str, Any]) -> NormalizedSourceRecord | None:
        try:
            title = item.get("title", "").strip()
            if not title:
                return None

            abstract = clean_html(item.get("abstractText") or "")
            doi = item.get("doi")
            pmid = item.get("pmid")
            pmcid = item.get("pmcid")

            external_id = pmid or pmcid or item.get("id")
            url = None
            if doi:
                url = f"https://doi.org/{doi}"
            elif pmcid:
                url = f"https://europepmc.org/article/PMC/{pmcid}"
            elif pmid:
                url = f"https://europepmc.org/article/MED/{pmid}"

            # Publication date
            pub_date = self._parse_date(item.get("firstPublicationDate") or item.get("pubYear"))

            journal = item.get("journalTitle") or item.get("bookOrReportDetails", {}).get("publisher")

            # Authors
            authors = []
            author_list = item.get("authorList", {}).get("author", [])
            for a in author_list[:10]:
                full = a.get("fullName") or f"{a.get('firstName', '')} {a.get('lastName', '')}".strip()
                if full:
                    authors.append(full)

            pub_type = item.get("pubType", "").lower()
            source = item.get("source", "").upper()
            is_preprint = source == "PPR" or "preprint" in pub_type
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
                external_id=str(external_id) if external_id else None,
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
    def _parse_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m", "%Y"):
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        return None
