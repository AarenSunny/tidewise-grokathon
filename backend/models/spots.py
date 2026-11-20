"""Region and spot configuration models."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from backend.models.common import Activity

_SPOT_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


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
    dungeness_prohibited: bool = False
    notes: Optional[str] = None

    @field_validator("id")
    @classmethod
    def _stable_spot_id(cls, v: str) -> str:
        if not _SPOT_ID_RE.match(v):
            raise ValueError(
                "spot id must be snake_case [a-z][a-z0-9_]{1,63} (stable ID, review1-#12)"
            )
        return v

    @field_validator("lat")
    @classmethod
    def _lat_range(cls, v: float) -> float:
        if v < -90 or v > 90:
            raise ValueError("lat out of range")
        return v

    @field_validator("lon")
    @classmethod
    def _lon_range(cls, v: float) -> float:
        if v < -180 or v > 180:
            raise ValueError("lon out of range")
        return v


class RegionConfig(BaseModel):
    id: str = "sf_bay_coast"
    name: str = "San Francisco Bay Area coast"
    bbox: tuple[float, float, float, float] = Field(
        default=(-123.0, 37.2, -121.7, 38.0),
        description="(min_lon, min_lat, max_lon, max_lat)",
    )
    timezone: str = "America/Los_Angeles"
    spots: list[Spot] = Field(default_factory=list)
