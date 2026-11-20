"""Crabbing scorer. Gear, season, and weights come from crabbing.yaml."""

from __future__ import annotations

from backend.scorers.base import BaseActivityScorer


class CrabbingScorer(BaseActivityScorer):
    activity_name = "crabbing"
