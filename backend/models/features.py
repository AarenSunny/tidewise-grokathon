"""Hourly feature grid produced by FeatureEngine."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.models.common import SourceStatus


class HourlyFeatures(BaseModel):
    """Derived signals for one spot at one hour (local region tz)."""

    hour: datetime
    # Tide
    tide_height_ft_mllw: Optional[float] = None
    tide_phase: Optional[str] = None  # rising | falling | high | low | slack
    is_slack_water: Optional[bool] = None
    is_minus_tide: Optional[bool] = None
    # Daylight / moon
    is_daylight: Optional[bool] = None
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None
    moon_phase: Optional[float] = None  # 0–1
    # Wind relative to shoreline
    wind_speed_kt: Optional[float] = None
    wind_gust_kt: Optional[float] = None
    wind_dir_deg: Optional[float] = None
    wind_onshore_component_kt: Optional[float] = None
    gust_spread_kt: Optional[float] = None
    # Waves
    wave_height_m: Optional[float] = None
    wave_period_s: Optional[float] = None
    # SST / chlorophyll
    sst_c: Optional[float] = None
    sst_anomaly_c: Optional[float] = None
    chl_bloom_flag: Optional[bool] = None
    # Alerts (names of active alerts intersecting this hour)
    active_alerts: list[str] = Field(default_factory=list)
    # Provenance for confidence
    source_statuses: dict[str, SourceStatus] = Field(default_factory=dict)


class SpotFeatureGrid(BaseModel):
    spot_id: str
    hours: list[HourlyFeatures] = Field(default_factory=list)
