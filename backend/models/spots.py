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
    shoreline_orientation_deg: Optional[float] = None
    activities: list[Activity] = Field(default_factory=list)
    tide_station_id: Optional[str] = None
    current_station_id: Optional[str] = None
    buoy_ids: list[str] = Field(default_factory=list)
    nws_grid: Optional[str] = None
    nws_zone: Optional[str] = None
    county: Optional[str] = None
    no_take: bool = False
    # 14 CCR §29.85(b)(1) — Dungeness prohibited (SF Bay / San Pablo Bay)
    dungeness_prohibited: bool = False
    notes: Optional[str] = None


class RegionConfig(BaseModel):
    id: str = "sf_bay_coast"
    name: str = "San Francisco Bay Area coast"
    bbox: tuple[float, float, float, float] = Field(
        default=(-123.0, 37.2, -121.7, 38.0),
        description="(min_lon, min_lat, max_lon, max_lat)",
    )
    timezone: str = "America/Los_Angeles"
    spots: list[Spot] = Field(default_factory=list)
