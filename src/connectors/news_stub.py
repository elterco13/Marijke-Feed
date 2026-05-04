"""
News/Communications stub connector.
Architecture is in place; extend with actual news APIs in future.
"""

from __future__ import annotations

import logging

from src.connectors.base import BaseConnector
from src.config.settings import Settings
from src.db.models import Profile
from src.schemas.source_record import NormalizedSourceRecord

logger = logging.getLogger(__name__)


class NewsStubConnector(BaseConnector):
    connector_key = "news_stub"
    display_name = "News & Communications (stub)"
    source_family = "news"

    def __init__(self, settings: Settings):
        super().__init__(settings)

    def run(self, profile: Profile, query: str) -> list[NormalizedSourceRecord]:
        self.log_info(f"News connector stub called for '{profile.name}'")
        # Future: integrate NewsAPI, GDELT, institutional newsroom scrapers, etc.
        # Each source would follow the same BaseConnector pattern.
        return []
