"""Enums and small shared types."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


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


class Confidence(BaseModel):
    """0–1 confidence derived from input freshness/status."""

    value: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
