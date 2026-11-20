"""HTTP request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from backend.models.common import Activity, require_aware
from backend.models.intent import QueryIntent
from backend.models.scoring import SpotRecommendation
from backend.models.sources import AdapterHealth
from backend.models.spots import Spot


class QueryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ClarifyingQuestion(BaseModel):
    question: str
    partial_intent: QueryIntent


class QueryResponse(BaseModel):
    intent: Optional[QueryIntent] = None
    clarifying: Optional[ClarifyingQuestion] = None
    recommendations: list[SpotRecommendation] = Field(default_factory=list)
    explanation: Optional[str] = None
    health: list[AdapterHealth] = Field(default_factory=list)
    scorer: Optional[str] = None
    note: Optional[str] = None
    mode: str = "live"


class RecommendResponse(BaseModel):
    activity: Activity
    spot_ids: list[str] = Field(default_factory=list)
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    recommendations: list[SpotRecommendation] = Field(default_factory=list)
    health: list[AdapterHealth] = Field(default_factory=list)
    note: Optional[str] = None
    distances_km: dict[str, float] = Field(default_factory=dict)
    # additive (phase3-e2e): which scorer produced the windows; "activity_scorers" or "unavailable"
    scorer: Optional[str] = None
    mode: str = "live"

    @field_validator("start", "end", mode="after")
    @classmethod
    def _aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        return require_aware(v)


class HealthResponse(BaseModel):
    status: str  # ok | degraded | down | unknown
    adapters: list[AdapterHealth] = Field(default_factory=list)
    checked_at: datetime


class SpotsResponse(BaseModel):
    region_id: str
    spots: list[Spot]


class ScoreWindowResponse(BaseModel):
    """One recommended window. Always populated — callers must not return an empty window."""

    activity: Activity
    location: str
    spot_id: str
    start: datetime
    end: datetime
    score: float = Field(ge=0.0, le=100.0)
    reason: str = Field(min_length=1)

    @field_validator("start", "end", mode="after")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        return require_aware(v)

    @field_validator("reason")
    @classmethod
    def _reason_text(cls, v: str) -> str:
        text = v.strip()
        if not text:
            raise ValueError("reason must be non-empty")
        return text
