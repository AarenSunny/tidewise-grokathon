"""Adapter result and health contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from backend.models.common import SourceStatus, require_aware


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
    # Newest sample timestamp in the payload (UTC). Used for freshness (review1-#2).
    observed_at: Optional[datetime] = None
    # Payload model class path for cache rehydration (review1-#5), e.g. "backend.adapters.coops.TidePayload"
    data_type: Optional[str] = None

    @field_validator("fetched_at", "valid_until", "observed_at", mode="after")
    @classmethod
    def _aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        return require_aware(v)


class AdapterHealth(BaseModel):
    """Per-adapter health snapshot for GET /health and the UI panel."""

    source_name: str
    status: SourceStatus = SourceStatus.unknown
    last_success_at: Optional[datetime] = None
    last_error_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_latency_ms: Optional[float] = None
    consecutive_failures: int = 0
    forced_down: bool = False
