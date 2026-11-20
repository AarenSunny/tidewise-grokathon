"""Sailing scorer. Gates and weights come from sailing.yaml."""

from __future__ import annotations

from backend.scorers.base import BaseActivityScorer


class SailingScorer(BaseActivityScorer):
    activity_name = "sailing"
