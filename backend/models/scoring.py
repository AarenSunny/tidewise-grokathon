"""Scorer outputs: ranked windows with factor breakdowns."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from backend.models.common import Confidence, GateResult


class FactorVerdict(str, Enum):
    """How to read one explainable factor. Unconfirmed inputs never look good."""

    good = "good"
    fair = "fair"
    poor = "poor"
    blocked = "blocked"
    cannot_confirm = "cannot_confirm"


class FactorBreakdown(BaseModel):
    """One explainable input behind a score.

    Frontend and API should read this shape:
    name, value, unit, verdict (good|fair|poor|blocked|cannot_confirm),
    source, observed_at, age_minutes. ``note`` carries the human reason
    when a gate is blocked or cannot be confirmed. ``weight`` and
    ``contribution`` are the scorer's own math, not measurements.
    """

    name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    verdict: Optional[FactorVerdict] = None
    source: Optional[str] = None
    observed_at: Optional[datetime] = None
    age_minutes: Optional[float] = None
    weight: float = 0.0
    contribution: float = 0.0
    note: Optional[str] = None


class ScoredWindow(BaseModel):
    spot_id: str
    start: datetime
    end: datetime
    score: float = Field(ge=0.0, le=100.0)
    confidence: Confidence
    gates: list[GateResult] = Field(default_factory=list)
    factors: list[FactorBreakdown] = Field(default_factory=list)
    # Deny by default. Callers must set True only after every gate passed.
    eligible: bool = False
    summary: Optional[str] = None
    # Short label for a ranked window, e.g. "Best clamming: Sat 6:10-8:30 AM, minus tide".
    label: Optional[str] = None


class SpotRecommendation(BaseModel):
    spot_id: str
    spot_name: str
    windows: list[ScoredWindow] = Field(default_factory=list)
    best_score: Optional[float] = None
