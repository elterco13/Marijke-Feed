"""
Source registry: maps connector keys to connector classes.
Enables/disables connectors based on settings and profile config.
"""

from __future__ import annotations

from typing import Type

from src.connectors.base import BaseConnector
from src.connectors.openalex import OpenAlexConnector
from src.connectors.crossref import CrossrefConnector
from src.connectors.europepmc import EuropePMCConnector
from src.connectors.pubmed import PubMedConnector
from src.connectors.rss import RSSConnector
from src.connectors.news_stub import NewsStubConnector
from src.config.settings import Settings

_REGISTRY: dict[str, Type[BaseConnector]] = {
    "openalex": OpenAlexConnector,
    "crossref": CrossrefConnector,
    "europepmc": EuropePMCConnector,
    "pubmed": PubMedConnector,
    "rss": RSSConnector,
    "news_stub": NewsStubConnector,
}

_SETTINGS_TOGGLE_MAP: dict[str, str] = {
    "openalex": "enable_connector_openalex",
    "crossref": "enable_connector_crossref",
    "europepmc": "enable_connector_europepmc",
    "pubmed": "enable_connector_pubmed",
    "rss": "enable_connector_rss",
    "news_stub": "enable_connector_news",
}


def get_all_connector_keys() -> list[str]:
    return list(_REGISTRY.keys())


def get_connector_display_names() -> dict[str, str]:
    """Return {key: display_name} for all registered connectors."""
    settings = Settings()
    return {
        key: cls(settings).display_name
        for key, cls in _REGISTRY.items()
    }


def build_connectors(
    enabled_keys: list[str],
    settings: Settings,
) -> list[BaseConnector]:
    """
    Build instantiated connector objects for the given keys,
    respecting both the profile-level enabled list and global settings toggles.
    """
    connectors: list[BaseConnector] = []
    for key in enabled_keys:
        cls = _REGISTRY.get(key)
        if cls is None:
            continue

        # Check global settings toggle
        toggle_attr = _SETTINGS_TOGGLE_MAP.get(key)
        if toggle_attr and not getattr(settings, toggle_attr, True):
            continue

        connectors.append(cls(settings))

    return connectors


def get_default_enabled_keys(settings: Settings) -> list[str]:
    """Return connector keys that are enabled by default in settings."""
    result = []
    for key, toggle_attr in _SETTINGS_TOGGLE_MAP.items():
        if getattr(settings, toggle_attr, False):
            result.append(key)
    return result
