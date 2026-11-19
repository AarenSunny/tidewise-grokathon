"""Scorer outputs: ranked windows with factor breakdowns."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.models.common import Confidence, GateResult


class FactorBreakdown(BaseModel):
    name: str
    value: Optional[float] = None
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
    eligible: bool = True
    summary: Optional[str] = None


class SpotRecommendation(BaseModel):
    spot_id: str
    spot_name: str
    windows: list[ScoredWindow] = Field(default_factory=list)
    best_score: Optional[float] = None
