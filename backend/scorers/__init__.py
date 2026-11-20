"""Activity scorers. Config lives in backend/config/activities."""

from __future__ import annotations

from typing import Any

from backend.scorers.base import BaseActivityScorer
from backend.scorers.clamming import ClammingScorer
from backend.scorers.crabbing import CrabbingScorer
from backend.scorers.sailing import SailingScorer
from backend.scorers.swimming import SwimmingScorer
from backend.scorers.windows import best_windows

_SCORERS: dict[str, type[BaseActivityScorer]] = {
    "clamming": ClammingScorer,
    "crabbing": CrabbingScorer,
    "swimming": SwimmingScorer,
    "sailing": SailingScorer,
}


def get_scorer(activity: str, config: dict[str, Any] | None = None) -> BaseActivityScorer:
    try:
        scorer_type = _SCORERS[activity]
    except KeyError as exc:
        raise KeyError(f"unknown activity {activity!r}") from exc
    if config is None:
        return scorer_type()
    return scorer_type(config=config)


__all__ = [
    "BaseActivityScorer",
    "ClammingScorer",
    "CrabbingScorer",
    "SailingScorer",
    "SwimmingScorer",
    "best_windows",
    "get_scorer",
]
