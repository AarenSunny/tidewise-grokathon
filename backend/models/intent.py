"""IntentBot structured output."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from backend.models.common import Activity, require_aware


class Preferences(BaseModel):
    """Soft preferences that scorers may weight; never override safety gates."""

    max_travel_km: Optional[float] = None
    prefer_morning: Optional[bool] = None
    avoid_crowds: Optional[bool] = None
    extra: dict[str, str] = Field(default_factory=dict)


class QueryIntent(BaseModel):
    """Typed intent extracted from natural language.

    If activity or location/spot_ids is missing, clarifying_question is set
    and the orchestrator should return that instead of scoring.
    """

    activity: Optional[Activity] = None
    location: Optional[str] = None
    spot_ids: list[str] = Field(default_factory=list)
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    preferences: Preferences = Field(default_factory=Preferences)
    clarifying_question: Optional[str] = None
    raw_text: Optional[str] = None

    @field_validator("start", "end", mode="after")
    @classmethod
    def _aware(cls, v: Optional[datetime]) -> Optional[datetime]:
        if v is None:
            return None
        return require_aware(v)

    @property
    def is_complete(self) -> bool:
        has_place = bool(self.location) or bool(self.spot_ids)
        return self.activity is not None and has_place
