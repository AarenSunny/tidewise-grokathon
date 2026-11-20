"""Swimming scorer. Gates and weights come from swimming.yaml."""

from __future__ import annotations

from backend.scorers.base import BaseActivityScorer


class SwimmingScorer(BaseActivityScorer):
    activity_name = "swimming"
