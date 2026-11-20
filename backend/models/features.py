"""Hourly feature grid produced by FeatureEngine."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator

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
    # Currents. CO-OPS Velocity_Major: ebb is negative, knots.
    current_velocity_kt: Optional[float] = None
    # SST / chlorophyll
    sst_c: Optional[float] = None
    sst_anomaly_c: Optional[float] = None
    chl_bloom_flag: Optional[bool] = None
    # Solar times for this hour's local date (America/Los_Angeles when annotated).
    civil_dawn: Optional[datetime] = None
    civil_dusk: Optional[datetime] = None
    # Alerts (names of active alerts intersecting this hour)
    active_alerts: list[str] = Field(default_factory=list)
    # Provenance for confidence
    source_statuses: dict[str, SourceStatus] = Field(default_factory=dict)


class ChlorophyllObservation(BaseModel):
    """VIIRS chlorophyll-a for one spot (CoastWatch ERDDAP, linear mg m^-3).

    Another session fills this from the live adapter. Scorers only read it.
    ``observed_at`` is the composite time in UTC (timezone-aware).
    ``pseudo_nitzschia_p`` is optional C-HARM P(cells > 10,000 L^-1), not a
    chlorophyll threshold.
    """

    observed_at: datetime
    chl_mg_m3: Optional[float] = None
    pseudo_nitzschia_p: Optional[float] = None
    source_status: SourceStatus = SourceStatus.ok

    @model_validator(mode="after")
    def _observed_at_must_be_aware(self) -> "ChlorophyllObservation":
        if self.observed_at.tzinfo is None or self.observed_at.tzinfo.utcoffset(self.observed_at) is None:
            raise ValueError("chlorophyll observed_at must be timezone-aware")
        return self


class BloomFlag(BaseModel):
    """Per-spot bloom flag for the map, with the observation time."""

    spot_id: str
    region_id: Optional[str] = None
    # True/False only when the reading can be judged. None when unconfirmed.
    bloom: Optional[bool] = None
    cannot_confirm: bool = True
    chl_mg_m3: Optional[float] = None
    observed_at: Optional[datetime] = None
    threshold_mg_m3: Optional[float] = None
    at_risk: Optional[bool] = None
    reason: str


class TideSample(BaseModel):
    """One CO-OPS tide prediction (ft MLLW). ``kind`` is H, L, or empty for 6-minute data."""

    time: datetime
    height_ft_mllw: float
    kind: Optional[str] = None

    @model_validator(mode="after")
    def _time_must_be_aware(self) -> "TideSample":
        if self.time.tzinfo is None or self.time.tzinfo.utcoffset(self.time) is None:
            raise ValueError("tide sample time must be timezone-aware")
        return self


class CurrentSample(BaseModel):
    """One CO-OPS current prediction. Velocity is knots; ebb is negative."""

    time: datetime
    velocity_kt: float
    kind: Optional[str] = None

    @model_validator(mode="after")
    def _time_must_be_aware(self) -> "CurrentSample":
        if self.time.tzinfo is None or self.time.tzinfo.utcoffset(self.time) is None:
            raise ValueError("current sample time must be timezone-aware")
        return self


class ConditionWindow(BaseModel):
    """A contiguous tide, current, or daylight window.

    Times are America/Los_Angeles. ``extremum_value`` is the low tide (ft MLLW)
    or the lowest absolute current (knots). Daylight windows leave it empty.
    """

    start: datetime
    end: datetime
    extremum_value: Optional[float] = None
    extremum_at: Optional[datetime] = None
    duration_hours: float
    kind: str
    score: float
    rank: int


class SpotFeatureGrid(BaseModel):
    spot_id: str
    hours: list[HourlyFeatures] = Field(default_factory=list)
    chlorophyll: Optional[ChlorophyllObservation] = None
    # outer_coast or sf_bay. None means the region is unknown.
    bloom_region: Optional[str] = None
