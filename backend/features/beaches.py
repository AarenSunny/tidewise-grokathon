"""Nearest valid spots for an activity.

A spot is valid when it allows the activity and its best window passes every
gate. Unknown closure, season, or bloom data is cannot_confirm and is not
valid. Distance is haversine miles. Order mixes distance with the best score.
"""

from __future__ import annotations

import math
from datetime import datetime

from pydantic import BaseModel, Field

from backend.config.safety import load_region_rules
from backend.models.common import Activity
from backend.models.features import CurrentSample, SpotFeatureGrid, TideSample
from backend.models.scoring import ScoredWindow
from backend.models.spots import Spot
from backend.scorers.windows import ranked_windows

EARTH_RADIUS_MI = 3958.7613


class RankedSpot(BaseModel):
    spot_id: str
    spot_name: str
    distance_mi: float
    best_score: float | None = None
    best_window: ScoredWindow | None = None
    valid: bool = False
    cannot_confirm: bool = False
    reasons: list[str] = Field(default_factory=list)
    rank_value: float = 0.0


class SpotRankResult(BaseModel):
    valid: list[RankedSpot] = Field(default_factory=list)
    rejected: list[RankedSpot] = Field(default_factory=list)


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    chord = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(math.sqrt(chord))


def rank_spots(
    user_lat: float,
    user_lon: float,
    activity: Activity | str,
    start: datetime,
    end: datetime,
    spots: list[Spot],
    grids: dict[str, SpotFeatureGrid],
    *,
    gear: str | None = None,
    tides: dict[str, list[TideSample]] | None = None,
    currents: dict[str, list[CurrentSample]] | None = None,
) -> SpotRankResult:
    """Return valid spots ordered by distance and best window score."""

    activity_name = activity.value if isinstance(activity, Activity) else str(activity)
    rules = load_region_rules()
    ranking = rules.get("ranking", {})
    score_weight = float(ranking.get("score_weight", 0.65))
    distance_weight = float(ranking.get("distance_weight", 0.35))
    valid: list[RankedSpot] = []
    rejected: list[RankedSpot] = []
    for spot in spots:
        distance = haversine_miles(user_lat, user_lon, spot.lat, spot.lon)
        if activity_name not in {item.value if isinstance(item, Activity) else str(item) for item in spot.activities}:
            rejected.append(
                RankedSpot(
                    spot_id=spot.id,
                    spot_name=spot.name,
                    distance_mi=distance,
                    valid=False,
                    cannot_confirm=False,
                    reasons=[f"{activity_name} is not offered at this spot"],
                )
            )
            continue
        grid = grids.get(spot.id)
        if grid is None:
            rejected.append(
                RankedSpot(
                    spot_id=spot.id,
                    spot_name=spot.name,
                    distance_mi=distance,
                    valid=False,
                    cannot_confirm=True,
                    reasons=["feature grid is missing"],
                )
            )
            continue
        windows = ranked_windows(
            grid,
            activity_name,
            start,
            end,
            latitude=spot.lat,
            longitude=spot.lon,
            gear=gear,
            tides=None if tides is None else tides.get(spot.id),
            currents=None if currents is None else currents.get(spot.id),
            as_of=start,
        )
        eligible = [window for window in windows if window.eligible]
        if eligible:
            best = max(eligible, key=lambda window: window.score)
            rank_value = score_weight * (best.score / 100.0) + distance_weight * (1.0 / (1.0 + distance))
            valid.append(
                RankedSpot(
                    spot_id=spot.id,
                    spot_name=spot.name,
                    distance_mi=distance,
                    best_score=best.score,
                    best_window=best,
                    valid=True,
                    cannot_confirm=False,
                    reasons=[],
                    rank_value=rank_value,
                )
            )
            continue
        cannot = any(gate.cannot_confirm for window in windows for gate in window.gates) or not windows
        reasons = []
        for window in windows:
            reasons.extend(gate.reason for gate in window.gates if not gate.passed or gate.cannot_confirm)
        if not reasons:
            reasons.append("no passing window in range")
        rejected.append(
            RankedSpot(
                spot_id=spot.id,
                spot_name=spot.name,
                distance_mi=distance,
                best_score=windows[0].score if windows else None,
                best_window=windows[0] if windows else None,
                valid=False,
                cannot_confirm=cannot,
                reasons=reasons,
            )
        )
    valid.sort(key=lambda spot: (-spot.rank_value, spot.distance_mi, spot.spot_id))
    return SpotRankResult(valid=valid, rejected=rejected)
