"""Adapter result and health contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.models.common import SourceStatus


class SourceResult(BaseModel):
    """Normalized return value from every source adapter."""

    data: Any = None
    fetched_at: datetime
    valid_until: datetime
    status: SourceStatus
    source_name: str
    notes: list[str] = Field(default_factory=list)
    cache_hit: bool = False
    fallback_used: Optional[str] = None
    latency_ms: Optional[float] = None


class AdapterHealth(BaseModel):
    """Per-adapter health snapshot for GET /health and the UI panel."""

    source_name: str
    status: SourceStatus
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_latency_ms: Optional[float] = None
    consecutive_failures: int = 0
    forced_down: bool = False
