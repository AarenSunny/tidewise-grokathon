"""Shared pydantic contracts for TideWise."""

from backend.models.common import (
    Activity,
    SourceStatus,
    GateResult,
    Confidence,
)
from backend.models.intent import QueryIntent, Preferences
from backend.models.spots import Spot, RegionConfig
from backend.models.sources import SourceResult, AdapterHealth
from backend.models.features import (
    BloomFlag,
    ChlorophyllObservation,
    ConditionWindow,
    CurrentSample,
    HourlyFeatures,
    SpotFeatureGrid,
    TideSample,
)
from backend.models.scoring import (
    FactorBreakdown,
    FactorVerdict,
    ScoredWindow,
    SpotRecommendation,
)
from backend.models.api import (
    QueryRequest,
    QueryResponse,
    RecommendResponse,
    HealthResponse,
    SpotsResponse,
    ClarifyingQuestion,
)

__all__ = [
    "Activity",
    "SourceStatus",
    "GateResult",
    "Confidence",
    "QueryIntent",
    "Preferences",
    "Spot",
    "RegionConfig",
    "SourceResult",
    "AdapterHealth",
    "BloomFlag",
    "ChlorophyllObservation",
    "ConditionWindow",
    "CurrentSample",
    "HourlyFeatures",
    "SpotFeatureGrid",
    "TideSample",
    "FactorBreakdown",
    "FactorVerdict",
    "ScoredWindow",
    "SpotRecommendation",
    "QueryRequest",
    "QueryResponse",
    "RecommendResponse",
    "HealthResponse",
    "SpotsResponse",
    "ClarifyingQuestion",
]
