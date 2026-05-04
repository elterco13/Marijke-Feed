"""
Database initialization: create tables and seed default data.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.db.base import Base
from src.db.session import get_engine, get_session

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).parent.parent.parent / "data"


def initialize_database() -> None:
    """Create all tables and seed initial data if needed."""
    engine = get_engine()
    # Ensure data dir exists
    db_path = Path(engine.url.database) if engine.url.database else Path("data/app.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Ensure exports dir exists
    exports_dir = Path(__file__).parent.parent.parent / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)

    # Import models to register them
    from src.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified.")

    _seed_connectors()
    _seed_rss_sources()


def _seed_connectors() -> None:
    """Seed default connector records if not already present."""
    from src.db.models import Connector

    default_connectors = [
        {
            "name": "OpenAlex",
            "connector_key": "openalex",
            "source_family": "academic",
            "enabled_by_default": True,
            "config_json": json.dumps({"base_url": "https://api.openalex.org"}),
        },
        {
            "name": "Crossref",
            "connector_key": "crossref",
            "source_family": "academic",
            "enabled_by_default": True,
            "config_json": json.dumps({"base_url": "https://api.crossref.org"}),
        },
        {
            "name": "Europe PMC",
            "connector_key": "europepmc",
            "source_family": "academic",
            "enabled_by_default": True,
            "config_json": json.dumps({"base_url": "https://www.ebi.ac.uk/europepmc/webservices/rest"}),
        },
        {
            "name": "PubMed (NCBI)",
            "connector_key": "pubmed",
            "source_family": "academic",
            "enabled_by_default": True,
            "config_json": json.dumps({"base_url": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"}),
        },
        {
            "name": "RSS Feeds",
            "connector_key": "rss",
            "source_family": "rss",
            "enabled_by_default": True,
            "config_json": json.dumps({}),
        },
        {
            "name": "News & Communications (stub)",
            "connector_key": "news_stub",
            "source_family": "news",
            "enabled_by_default": False,
            "config_json": json.dumps({}),
        },
    ]

    with get_session() as session:
        for conn_data in default_connectors:
            existing = session.query(Connector).filter_by(connector_key=conn_data["connector_key"]).first()
            if not existing:
                connector = Connector(**conn_data)
                session.add(connector)
        session.commit()
    logger.info("Connectors seeded.")


def _seed_rss_sources() -> None:
    """Seed default RSS feeds from seed file."""
    from src.db.models import SavedSource

    seed_file = _DATA_DIR / "starter_sources.json"
    if not seed_file.exists():
        return

    with open(seed_file, encoding="utf-8") as f:
        sources = json.load(f)

    with get_session() as session:
        for source in sources:
            existing = session.query(SavedSource).filter_by(url=source["url"]).first()
            if not existing:
                ss = SavedSource(
                    name=source.get("name", "Unknown"),
                    url=source["url"],
                    source_type=source.get("source_type", "rss"),
                    source_family=source.get("source_family", "rss"),
                    is_enabled=source.get("is_enabled", True),
                    notes=source.get("notes"),
                )
                session.add(ss)
        session.commit()
    logger.info("RSS sources seeded.")
