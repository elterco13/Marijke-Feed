"""
Search orchestration service.
Coordinates: profile load → connector dispatch → normalize → dedupe → score → persist.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from src.config.settings import get_settings
from src.db.models import Profile, Result, SearchRun
from src.db.session import get_session
from src.schemas.source_record import NormalizedSourceRecord
from src.services.dedupe_service import deduplicate
from src.services.normalization_service import normalize_records
from src.services.scoring_service import score_records
from src.services.source_registry import build_connectors
from src.services.taxonomy_service import extract_taxa
from src.services.query_builder import build_query

logger = logging.getLogger(__name__)


class SearchService:
    """Orchestrates a full search run for a profile."""

    def __init__(self, on_progress=None):
        self.settings = get_settings()
        self.on_progress = on_progress  # optional callback(msg: str, pct: float)

    def run_search(self, profile: Profile, enabled_connector_keys: list[str]) -> dict[str, Any]:
        """
        Execute a full search run. Returns summary dict.
        profile is a detached ORM object — we use its ID to reload as needed.
        """
        self._progress("Starting search run...", 0.0)

        profile_id = profile.id

        # Create run record and get its ID
        run_id = self._create_run(profile_id)

        try:
            self._update_run(run_id, status="running")

            # 1. Fetch from connectors
            self._progress("Fetching from sources...", 0.1)
            connectors = build_connectors(enabled_connector_keys, self.settings)
            if not connectors:
                raise ValueError("No connectors enabled.")

            raw_records: list[NormalizedSourceRecord] = []
            total_connectors = len(connectors)
            
            # Compose the query using the Feed Builder ontology
            composed_query = build_query(profile)
            self._progress(f"Composed Query: {composed_query}", 0.15)
            
            for idx, connector in enumerate(connectors):
                self._progress(f"Fetching: {connector.display_name}...", 0.15 + 0.4 * (idx / total_connectors))
                try:
                    results = connector.run(profile, composed_query)
                    raw_records.extend(results)
                    logger.info(f"Connector {connector.connector_key}: {len(results)} records")
                except Exception as e:
                    logger.error(f"Connector {connector.connector_key} failed: {e}")

            total_raw = len(raw_records)

            # 2. Normalize
            self._progress("Normalizing results...", 0.55)
            normalized = normalize_records(raw_records)
            total_normalized = len(normalized)

            # 3. Deduplicate
            self._progress("Deduplicating...", 0.65)
            deduped = deduplicate(normalized)
            total_deduped = len(deduped)

            # 4. Score and categorize
            self._progress("Scoring relevance...", 0.75)
            scored = score_records(deduped, include_preprints=profile.include_preprints)

            # 5. Extract taxa
            self._progress("Extracting taxa...", 0.85)
            final_records = []
            for record in scored:
                text = record.get_text_for_scoring()
                species, taxa = extract_taxa(text)
                record = record.model_copy(update={"species": species, "taxa": taxa})
                final_records.append(record)

            # 6. Persist results
            self._progress("Saving to database...", 0.92)
            self._persist_results(run_id, profile_id, final_records)

            # Update run status
            self._update_run(
                run_id,
                status="done",
                finished_at=datetime.utcnow(),
                total_raw_results=total_raw,
                total_normalized_results=total_normalized,
                total_deduped_results=total_deduped,
            )

            self._progress("Done!", 1.0)
            logger.info(
                f"Run {run_id} complete: {total_raw} raw → "
                f"{total_normalized} normalized → "
                f"{total_deduped} deduped → "
                f"{len(final_records)} scored"
            )

            return {
                "run_id": run_id,
                "status": "done",
                "total_raw": total_raw,
                "total_normalized": total_normalized,
                "total_deduped": total_deduped,
                "total_final": len(final_records),
            }

        except Exception as e:
            logger.error(f"Search run failed: {e}", exc_info=True)
            self._update_run(
                run_id,
                status="error",
                notes=str(e),
                finished_at=datetime.utcnow(),
            )
            return {"run_id": run_id, "status": "error", "error": str(e)}

    def _create_run(self, profile_id: int) -> int:
        """Create a SearchRun record and return its ID."""
        with get_session() as session:
            run = SearchRun(
                profile_id=profile_id,
                started_at=datetime.utcnow(),
                status="pending",
            )
            session.add(run)
            session.commit()
            return run.id

    def _update_run(self, run_id: int, **kwargs) -> None:
        """Update fields on a SearchRun record."""
        with get_session() as session:
            run = session.query(SearchRun).get(run_id)
            if run:
                for k, v in kwargs.items():
                    setattr(run, k, v)
                session.commit()

    def _persist_results(
        self,
        run_id: int,
        profile_id: int,
        records: list[NormalizedSourceRecord],
    ) -> None:
        with get_session() as session:
            for record in records:
                result = Result(
                    run_id=run_id,
                    profile_id=profile_id,
                    source_connector=record.source_connector,
                    source_family=record.source_family,
                    source_name=record.source_name,
                    external_id=record.external_id,
                    doi=record.doi,
                    title=record.title,
                    abstract_or_summary=record.abstract_or_summary,
                    short_description=record.short_description,
                    url=record.url,
                    image_url=record.image_url,
                    published_at=record.published_at,
                    journal_or_outlet=record.journal_or_outlet,
                    authors_json=json.dumps(record.authors),
                    category=record.category,
                    subcategory=record.subcategory,
                    species_json=json.dumps(record.species),
                    taxa_json=json.dumps(record.taxa),
                    content_type=record.content_type,
                    is_preprint=record.is_preprint,
                    relevance_score=record.relevance_score,
                    relevance_explanation_json=json.dumps(record.relevance_explanation),
                    raw_payload_json=json.dumps(record.raw_payload) if record.raw_payload else None,
                    normalized_hash=record.normalized_hash,
                    duplicate_group_key=record.duplicate_group_key,
                )
                session.add(result)
            session.commit()

    def _progress(self, msg: str, pct: float) -> None:
        logger.info(f"[{pct:.0%}] {msg}")
        if self.on_progress:
            self.on_progress(msg, pct)
