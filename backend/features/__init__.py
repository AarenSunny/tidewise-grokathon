"""Feature calculations: solar time, moon phase, tide windows, bloom, ranking."""

from backend.features.beaches import RankedSpot, SpotRankResult, haversine_miles, rank_spots
from backend.features.bloom import bloom_status
from backend.features.daylight import annotate_daylight
from backend.features.moon import annotate_moon, moon_phase
from backend.features.solar import solar_times
from backend.features.tides import (
    find_clamming_windows,
    find_crabbing_windows,
    find_daylight_windows,
    find_ebb_windows,
)

__all__ = [
    "RankedSpot",
    "SpotRankResult",
    "annotate_daylight",
    "annotate_moon",
    "bloom_status",
    "find_clamming_windows",
    "find_crabbing_windows",
    "find_daylight_windows",
    "find_ebb_windows",
    "haversine_miles",
    "moon_phase",
    "rank_spots",
    "solar_times",
]
