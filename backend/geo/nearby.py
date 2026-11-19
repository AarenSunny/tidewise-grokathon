"""Haversine distance and nearest-spot selection."""

from __future__ import annotations

import math
from typing import Optional

from backend.models.common import Activity
from backend.models.spots import Spot


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_spots(
    spots: list[Spot],
    *,
    lat: float,
    lon: float,
    activity: Optional[Activity] = None,
    limit: int = 6,
) -> list[tuple[Spot, float]]:
    """Return up to `limit` spots sorted by distance (km), optionally filtered by activity."""
    candidates = spots
    if activity is not None:
        candidates = [s for s in spots if activity in s.activities]
    ranked = sorted(
        ((s, haversine_km(lat, lon, s.lat, s.lon)) for s in candidates),
        key=lambda x: x[1],
    )
    return ranked[:limit]
