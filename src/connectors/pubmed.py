"""
PubMed connector using NCBI E-utilities.
https://www.ncbi.nlm.nih.gov/books/NBK25500/
"""

from __future__ import annotations

import logging
import time
import xml.etree.ElementTree as ET
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

NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedConnector(BaseConnector):
    connector_key = "pubmed"
    display_name = "PubMed"
    source_family = "academic"

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.base_url = NCBI_BASE
        self.api_key = settings.pubmed_api_key
        # Without API key: max 3 req/sec; with key: 10 req/sec
        self.request_delay = 0.34 if not self.api_key else 0.1

    def run(self, profile: Profile, query: str) -> list[NormalizedSourceRecord]:
        self.log_info(f"Starting search for profile '{profile.name}'")
        records: list[NormalizedSourceRecord] = []

        from_date = days_ago_date(profile.date_window_days)
        limit = min(profile.result_limit, 200)  # PubMed eutils caps per request

        try:
            pmids = self._esearch(query, from_date, limit)
            if not pmids:
                self.log_info("No results from esearch.")
                return records
            raw_articles = self._efetch(pmids)
        except Exception as e:
            self.log_error(f"Fetch failed: {e}")
            return records

        for article in raw_articles:
            record = self._normalize(article)
            if record:
                records.append(record)

        self.log_info(f"Returned {len(records)} records.")
        return records

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    def _get(self, endpoint: str, params: dict[str, Any]) -> httpx.Response:
        if self.api_key:
            params["api_key"] = self.api_key
        params["tool"] = "AquariumScienceMonitor"
        params["email"] = self.settings.contact_email
        headers = {"User-Agent": self.settings.user_agent}
        with httpx.Client(timeout=self.settings.request_timeout) as client:
            resp = client.get(f"{self.base_url}/{endpoint}", params=params, headers=headers)
            resp.raise_for_status()
        time.sleep(self.request_delay)
        return resp

    def _esearch(self, query: str, from_date: str, limit: int) -> list[str]:
        """Get list of PMIDs from eSearch."""
        # Build date range
        from_parts = from_date.split("-")
        from_date_ncbi = f"{from_parts[0]}/{from_parts[1]}/{from_parts[2]}" if len(from_parts) == 3 else from_date

        params = {
            "db": "pubmed",
            "term": query,
            "retmax": limit,
            "sort": "pub date",
            "retmode": "json",
            "datetype": "pdat",
            "mindate": from_date_ncbi,
            "maxdate": "3000",
        }
        resp = self._get("esearch.fcgi", params)
        data = resp.json()
        return data.get("esearchresult", {}).get("idlist", [])

    def _efetch(self, pmids: list[str]) -> list[ET.Element]:
        """Fetch article details for a list of PMIDs."""
        # Fetch in batches of 50
        articles: list[ET.Element] = []
        batch_size = 50
        for i in range(0, len(pmids), batch_size):
            batch = pmids[i : i + batch_size]
            params = {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
                "rettype": "abstract",
            }
            resp = self._get("efetch.fcgi", params)
            try:
                root = ET.fromstring(resp.text)
                articles.extend(root.findall(".//PubmedArticle"))
            except ET.ParseError as e:
                self.log_error(f"XML parse error: {e}")
        return articles

    def _normalize(self, article: ET.Element) -> NormalizedSourceRecord | None:
        try:
            medline = article.find("MedlineCitation")
            if medline is None:
                return None

            art = medline.find("Article")
            if art is None:
                return None

            # Title
            title_el = art.find("ArticleTitle")
            title = "".join(title_el.itertext()) if title_el is not None else ""
            if not title:
                return None

            # Abstract
            abstract_parts = art.findall(".//AbstractText")
            abstract_text = " ".join("".join(p.itertext()) for p in abstract_parts).strip()

            # PMID
            pmid_el = medline.find("PMID")
            pmid = pmid_el.text if pmid_el is not None else None

            # DOI
            doi = None
            for id_el in article.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text
                    break

            url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None
            if doi:
                url = f"https://doi.org/{doi}"

            # Published date
            pub_date = self._extract_pub_date(art)

            # Journal
            journal_el = art.find("Journal/Title")
            journal = journal_el.text if journal_el is not None else None

            # Authors
            authors = []
            for author_el in art.findall("AuthorList/Author")[:10]:
                last = author_el.findtext("LastName") or ""
                fore = author_el.findtext("ForeName") or author_el.findtext("Initials") or ""
                name = f"{fore} {last}".strip()
                if name:
                    authors.append(name)

            # Publication types
            pub_types = [pt.text for pt in medline.findall(".//PublicationType") if pt.text]
            is_preprint = any("preprint" in (pt or "").lower() for pt in pub_types)
            content_type = "preprint" if is_preprint else "article"

            return NormalizedSourceRecord(
                title=clean_html(title),
                abstract_or_summary=abstract_text or None,
                short_description=truncate_text(abstract_text, 200) if abstract_text else None,
                url=url,
                published_at=pub_date,
                journal_or_outlet=journal,
                authors=authors,
                doi=doi,
                external_id=pmid,
                source_connector=self.connector_key,
                source_family=self.source_family,
                source_name=self.display_name,
                content_type=content_type,
                is_preprint=is_preprint,
                raw_payload={"pmid": pmid, "doi": doi},
            )
        except Exception as e:
            self.log_error(f"Normalization error: {e}")
            return None

    @staticmethod
    def _extract_pub_date(art: ET.Element) -> datetime | None:
        for path in ("Journal/JournalIssue/PubDate", "ArticleDate"):
            date_el = art.find(path)
            if date_el is not None:
                year = date_el.findtext("Year")
                month = date_el.findtext("Month") or "Jan"
                day = date_el.findtext("Day") or "1"
                if year:
                    try:
                        return datetime.strptime(f"{year} {month} {day}", "%Y %b %d")
                    except ValueError:
                        try:
                            return datetime.strptime(f"{year} {month} {day}", "%Y %m %d")
                        except ValueError:
                            try:
                                return datetime(int(year), 1, 1)
                            except Exception:
                                pass
        return None
