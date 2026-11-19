"""HTTP request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.models.common import Activity
from backend.models.intent import QueryIntent
from backend.models.scoring import SpotRecommendation
from backend.models.sources import AdapterHealth
from backend.models.spots import Spot


class QueryRequest(BaseModel):
    text: str = Field(min_length=1)


class ClarifyingQuestion(BaseModel):
    question: str
    partial_intent: QueryIntent


class QueryResponse(BaseModel):
    intent: Optional[QueryIntent] = None
    clarifying: Optional[ClarifyingQuestion] = None
    recommendations: list[SpotRecommendation] = Field(default_factory=list)
    explanation: Optional[str] = None
    health: list[AdapterHealth] = Field(default_factory=list)


class RecommendResponse(BaseModel):
    activity: Activity
    spot_ids: list[str] = Field(default_factory=list)
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    recommendations: list[SpotRecommendation] = Field(default_factory=list)
    health: list[AdapterHealth] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str  # ok | degraded | down
    adapters: list[AdapterHealth] = Field(default_factory=list)
    checked_at: datetime


class SpotsResponse(BaseModel):
    region_id: str
    spots: list[Spot]
