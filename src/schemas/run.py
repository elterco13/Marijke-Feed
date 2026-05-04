"""
Run schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class RunSchema(BaseModel):
    id: Optional[int] = None
    profile_id: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    status: str = "pending"
    total_raw_results: int = 0
    total_normalized_results: int = 0
    total_deduped_results: int = 0
    notes: Optional[str] = None

    class Config:
        from_attributes = True
