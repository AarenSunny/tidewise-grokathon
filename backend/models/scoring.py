"""Scorer outputs: ranked windows with factor breakdowns."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from backend.models.common import Confidence, GateResult, require_aware


class FactorBreakdown(BaseModel):
    name: str
    value: Optional[float] = None
    weight: float = 0.0
    contribution: float = 0.0
    note: Optional[str] = None


class ScoredWindow(BaseModel):
    """Ranked time window. eligible defaults to False (deny-by-default, review1-#1).

    Callers may set eligible explicitly after evaluating gates, or leave it False.
    When gates are present, prefer deriving eligibility: every gate passed and none
    cannot_confirm. We keep an explicit field (default False) so incomplete
    construction cannot accidentally recommend.
    """

    spot_id: str
    start: datetime
    end: datetime
    score: float = Field(ge=0.0, le=100.0)
    confidence: Confidence
    gates: list[GateResult] = Field(default_factory=list)
    factors: list[FactorBreakdown] = Field(default_factory=list)
    # Default-deny: missing gates must never yield an eligible window (review1-#1).
    eligible: bool = False
    summary: Optional[str] = None

    @field_validator("start", "end", mode="after")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        return require_aware(v)

    @model_validator(mode="after")
    def _eligible_requires_every_gate_passed(self) -> "ScoredWindow":
        """review1-#1: eligible=True is only constructible when gates is non-empty and
        every gate passed with cannot_confirm False. Missing/failed gates never recommend."""
        if self.eligible and not (
            self.gates and all(g.passed and not g.cannot_confirm for g in self.gates)
        ):
            raise ValueError(
                "eligible=True requires a non-empty gates list with every gate passed "
                "and none cannot_confirm"
            )
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def gates_all_passed(self) -> bool:
        """True only when there is at least one gate and every gate passed."""
        if not self.gates:
            return False
        return all(g.passed and not g.cannot_confirm for g in self.gates)


class SpotRecommendation(BaseModel):
    spot_id: str
    spot_name: str
    windows: list[ScoredWindow] = Field(default_factory=list)
    best_score: Optional[float] = None
    distance_km: Optional[float] = None
