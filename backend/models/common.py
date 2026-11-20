"""Enums and small shared types."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


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


class GateResult(BaseModel):
    """Outcome of a hard safety gate.

    Missing evidence must NEVER pass. Use passed=False with
    reason indicating cannot_confirm when data is absent.
    """

    name: str
    passed: bool
    reason: str
    cannot_confirm: bool = False
    evidence: Optional[str] = None

    @model_validator(mode="after")
    def _unconfirmed_gate_cannot_pass(self) -> "GateResult":
        # Missing or unconfirmed evidence is not a pass.
        if self.passed and self.cannot_confirm:
            raise ValueError("a gate cannot pass when cannot_confirm is true")
        return self


class Confidence(BaseModel):
    """0–1 confidence derived from input freshness/status."""

    value: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
