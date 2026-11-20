"""Haversine distance and activity-aware spot selection for /recommend."""

from __future__ import annotations

import math
from typing import Optional

from backend.models.common import Activity
from backend.models.spots import Spot

# Take activities must not be offered at no-take sites. Crabbing in the Bay
# is a separate legal ban (14 CCR §29.85(b)(1)) via dungeness_prohibited.
_TAKE_ACTIVITIES = {Activity.clamming, Activity.crabbing}

BBox = tuple[float, float, float, float]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    arc = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(arc))


def validate_user_point(lat: float, lon: float) -> None:
    """Reject missing, non-finite, or out-of-range coordinates.

    A partial or garbage point must not fall through to "every spot".
    """
    if isinstance(lat, bool) or isinstance(lon, bool):
        raise ValueError("lat and lon must be finite numbers")
    if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
        raise ValueError("lat and lon must be finite numbers")
    if not math.isfinite(float(lat)) or not math.isfinite(float(lon)):
        raise ValueError("lat and lon must be finite numbers")
    if not -90.0 <= float(lat) <= 90.0 or not -180.0 <= float(lon) <= 180.0:
        raise ValueError("lat/lon out of range")


def in_bbox(lat: float, lon: float, bbox: BBox) -> bool:
    min_lon, min_lat, max_lon, max_lat = bbox
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def ineligibility_reason(spot: Spot, activity: Activity) -> Optional[str]:
    if activity not in spot.activities:
        return f"Spot {spot.id} does not support activity {activity.value}"
    if activity in _TAKE_ACTIVITIES and spot.no_take:
        return f"Spot {spot.id} is no-take and cannot be recommended for {activity.value}"
    if activity == Activity.crabbing and spot.dungeness_prohibited:
        return f"Spot {spot.id} is closed to Dungeness crab"
    return None


def activity_eligible(spot: Spot, activity: Activity) -> bool:
    return ineligibility_reason(spot, activity) is None


def nearest_spots(
    spots: list[Spot],
    *,
    lat: float,
    lon: float,
    activity: Optional[Activity] = None,
    limit: int = 6,
) -> list[tuple[Spot, float]]:
    """Up to `limit` spots sorted by distance (km), then spot id.

    When activity is set, no-take and Dungeness-prohibited spots are excluded
    for the activities those rules apply to.
    """
    candidates = spots
    if activity is not None:
        candidates = [s for s in spots if activity_eligible(s, activity)]
    ranked = sorted(
        ((s, haversine_km(lat, lon, s.lat, s.lon)) for s in candidates),
        key=lambda item: (item[1], item[0].id),
    )
    return ranked[: max(limit, 0)]


def select_spots(
    spots: list[Spot],
    activity: Activity,
    *,
    spot_id: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    limit: int = 6,
    bbox: Optional[BBox] = None,
) -> tuple[list[Spot], dict[str, float], list[str]]:
    """Resolve the spots a /recommend call should consider.

    Returns (spots, distances_km, note fragments).
    Unknown spot_id raises KeyError. An explicit ineligible spot, partial
    coordinates, or a non-finite point raises ValueError.
    """
    if (lat is None) ^ (lon is None):
        raise ValueError("lat and lon must be provided together")
    if lat is not None and lon is not None:
        validate_user_point(lat, lon)

    notes: list[str] = []
    distances: dict[str, float] = {}

    if spot_id:
        match = next((s for s in spots if s.id == spot_id), None)
        if match is None:
            raise KeyError(spot_id)
        reason = ineligibility_reason(match, activity)
        if reason:
            raise ValueError(reason)
        selected = [match]
        if lat is not None and lon is not None:
            distances[match.id] = round(haversine_km(lat, lon, match.lat, match.lon), 2)
    elif lat is not None and lon is not None:
        ranked = nearest_spots(spots, lat=lat, lon=lon, activity=activity, limit=limit)
        selected = [s for s, _ in ranked]
        distances = {s.id: round(d, 2) for s, d in ranked}
        if bbox is not None and not in_bbox(lat, lon, bbox):
            notes.append(
                "User location is outside the configured SF Bay Area coast bbox; "
                "distances are still to catalog spots."
            )
    else:
        selected = [s for s in spots if activity_eligible(s, activity)][:limit]

    if not selected:
        notes.append(f"No eligible spots for {activity.value}.")
    return selected, distances, notes
