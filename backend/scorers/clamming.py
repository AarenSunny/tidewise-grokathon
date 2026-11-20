"""Clamming scorer. Gates and weights come from clamming.yaml."""

from __future__ import annotations

from backend.scorers.base import BaseActivityScorer


class ClammingScorer(BaseActivityScorer):
    activity_name = "clamming"
