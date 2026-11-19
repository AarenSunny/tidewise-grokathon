"""Region and spot configuration models."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from backend.models.common import Activity


class Spot(BaseModel):
    """A recreation spot in the configured region."""

    id: str
    name: str
    lat: float
    lon: float
    # Shoreline orientation in degrees (0=N, 90=E) for wind relative scoring
    shoreline_orientation_deg: Optional[float] = None
    activities: list[Activity] = Field(default_factory=list)
    # Preferred station IDs per source (filled from DATA_SOURCES.md in later phases)
    tide_station_id: Optional[str] = None
    buoy_ids: list[str] = Field(default_factory=list)
    nws_grid: Optional[str] = None  # e.g. "MTR/88,126"
    notes: Optional[str] = None


class RegionConfig(BaseModel):
    """Config-driven region so the Bay Area can be extended later."""

    id: str = "sf_bay_coast"
    name: str = "San Francisco Bay Area coast"
    bbox: tuple[float, float, float, float] = Field(
        default=(-123.0, 37.2, -121.7, 38.0),
        description="(min_lon, min_lat, max_lon, max_lat)",
    )
    timezone: str = "America/Los_Angeles"
    spots: list[Spot] = Field(default_factory=list)
