"""
Application settings loaded from environment variables via pydantic-settings.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # Contact / identification
    openalex_email: str = Field(default="researcher@example.com", alias="OPENALEX_EMAIL")
    contact_email: str = Field(default="researcher@example.com", alias="CONTACT_EMAIL")

    # Database
    database_url: str = Field(default="sqlite:///./data/app.db", alias="DATABASE_URL")

    # HTTP
    request_timeout: int = Field(default=30, alias="REQUEST_TIMEOUT")
    user_agent: str = Field(
        default="AquariumScienceMonitor/1.0 (mailto:researcher@example.com)",
        alias="USER_AGENT",
    )

    # Defaults
    default_result_limit: int = Field(default=50, alias="DEFAULT_RESULT_LIMIT")
    default_date_window_days: int = Field(default=30, alias="DEFAULT_DATE_WINDOW_DAYS")

    # Connector toggles
    enable_connector_openalex: bool = Field(default=True, alias="ENABLE_CONNECTOR_OPENALEX")
    enable_connector_crossref: bool = Field(default=True, alias="ENABLE_CONNECTOR_CROSSREF")
    enable_connector_europepmc: bool = Field(default=True, alias="ENABLE_CONNECTOR_EUROPEPMC")
    enable_connector_pubmed: bool = Field(default=True, alias="ENABLE_CONNECTOR_PUBMED")
    enable_connector_rss: bool = Field(default=True, alias="ENABLE_CONNECTOR_RSS")
    enable_connector_news: bool = Field(default=False, alias="ENABLE_CONNECTOR_NEWS")

    # PubMed
    pubmed_api_key: str | None = Field(default=None, alias="PUBMED_API_KEY")

    # Logging
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "populate_by_name": True,
        "extra": "ignore",
    }

    @property
    def http_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
