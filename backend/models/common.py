"""Enums and small shared types."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class Activity(str, Enum):
    clamming = "clamming"
    crabbing = "crabbing"
    swimming = "swimming"
    sailing = "sailing"


class SourceStatus(str, Enum):
    ok = "ok"
    stale = "stale"
    down = "down"
    degraded = "degraded"
    unknown = "unknown"


def require_aware(dt: datetime) -> datetime:
    """Reject naive datetimes; require UTC-aware (or any tz)."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        raise ValueError("datetime must be timezone-aware (prefer UTC)")
    return dt


AwareDatetime = Annotated[datetime, Field(description="Timezone-aware datetime")]


class GateResult(BaseModel):
    """Outcome of a hard safety gate.

    Missing evidence must NEVER pass. When cannot_confirm is True,
    passed is forced False by a model_validator (review1-#1).
    """

    name: str
    passed: bool
    reason: str
    cannot_confirm: bool = False
    evidence: Optional[str] = None

    @model_validator(mode="after")
    def _missing_never_passes(self) -> GateResult:
        if self.cannot_confirm and self.passed:
            raise ValueError(
                "GateResult: cannot_confirm=True forbids passed=True "
                "(missing/unknown must never pass a safety gate)"
            )
        return self


class Confidence(BaseModel):
    """0–1 confidence derived from input freshness/status."""

    value: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
