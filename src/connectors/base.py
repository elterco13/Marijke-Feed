"""
Abstract base connector class.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.db.models import Profile
    from src.config.settings import Settings
    from src.schemas.source_record import NormalizedSourceRecord

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """All connectors must implement this interface."""

    connector_key: str = ""
    display_name: str = ""
    source_family: str = ""

    def __init__(self, settings: "Settings"):
        self.settings = settings

    @abstractmethod
    def run(self, profile: "Profile", query: str) -> list["NormalizedSourceRecord"]:
        """
        Execute the search based on the profile and composed query, returning normalized records.
        """
        ...

    def log_info(self, msg: str) -> None:
        logger.info(f"[{self.connector_key}] {msg}")

    def log_warning(self, msg: str) -> None:
        logger.warning(f"[{self.connector_key}] {msg}")

    def log_error(self, msg: str) -> None:
        logger.error(f"[{self.connector_key}] {msg}")
