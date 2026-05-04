"""
Profile schema for API-level usage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ProfileSchema(BaseModel):
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    is_active: bool = True
    query_text: str
    date_window_days: int = 30
    result_limit: int = 50
    include_preprints: bool = True
    enabled_connectors: list[str] = []
    include_keywords: list[str] = []
    exclude_keywords: list[str] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
