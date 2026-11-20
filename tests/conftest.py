"""Scorer fixtures. The live path must not import this module."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from backend.models.common import SourceStatus
from backend.models.features import ChlorophyllObservation, HourlyFeatures, SpotFeatureGrid

LA = ZoneInfo("America/Los_Angeles")
UTC = timezone.utc
HMB_LAT = 37.4636
HMB_LON = -122.4286


def aware(year, month, day, hour=0, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=LA)


@pytest.fixture
def la():
    return aware


@pytest.fixture
def hmb():
    return HMB_LAT, HMB_LON


def all_ok(**overrides) -> dict:
    statuses = {
        "coops_tides": SourceStatus.ok,
        "coops_currents": SourceStatus.ok,
        "alerts_shellfish": SourceStatus.ok,
        "alerts_bacteria": SourceStatus.ok,
        "nws_marine": SourceStatus.ok,
        "nws_alerts": SourceStatus.ok,
        "ndbc_buoy": SourceStatus.ok,
        "sst": SourceStatus.ok,
        "satellite_chl": SourceStatus.ok,
    }
    statuses.update(overrides)
    return statuses


def make_hour(moment: datetime, **overrides) -> HourlyFeatures:
    payload = dict(
        tide_height_ft_mllw=-1.2,
        tide_phase="slack",
        is_slack_water=True,
        wind_speed_kt=12.0,
        wind_gust_kt=14.0,
        gust_spread_kt=2.0,
        wave_height_m=0.4,
        sst_c=18.0,
        current_velocity_kt=0.2,
        active_alerts=[],
        source_statuses=all_ok(),
    )
    payload.update(overrides)
    if "source_statuses" in overrides:
        payload["source_statuses"] = overrides["source_statuses"]
    return HourlyFeatures(hour=moment, **payload)


def make_chl(value=2.0, when=None, status=SourceStatus.ok) -> ChlorophyllObservation:
    return ChlorophyllObservation(
        observed_at=when or datetime(2026, 11, 18, 9, tzinfo=UTC),
        chl_mg_m3=value,
        source_status=status,
    )


def make_grid(moment: datetime, spot_id="half_moon_bay", region="outer_coast", **hour_overrides) -> SpotFeatureGrid:
    return SpotFeatureGrid(
        spot_id=spot_id,
        hours=[make_hour(moment, **hour_overrides)],
        bloom_region=region,
        chlorophyll=make_chl(),
    )
