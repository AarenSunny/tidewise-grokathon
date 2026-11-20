"""Tide windows, solar time, bloom flag, distance ranking, and best-window labels."""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone

import pytest

from backend.config.safety import load_region_rules
from backend.features.beaches import haversine_miles, rank_spots
from backend.features.bloom import bloom_status
from backend.features.moon import moon_phase
from backend.features.solar import solar_times
from backend.features.tides import find_clamming_windows, find_crabbing_windows
from backend.models.common import Activity, SourceStatus
from backend.models.features import CurrentSample, TideSample
from backend.models.spots import Spot
from backend.scorers import best_windows, get_scorer
from tests.conftest import HMB_LAT, HMB_LON, LA, UTC, aware, make_chl, make_grid, make_hour

from backend.models.features import SpotFeatureGrid


def _tide(moment, height, kind=None) -> TideSample:
    return TideSample(time=moment, height_ft_mllw=height, kind=kind)


def test_noaa_sunrise_sunset_half_moon_bay():
    # NOAA solar calculator table for 37.4636 N, 122.4286 W on 2026-11-19:
    # sunrise 06:54, sunset 16:56 local (PST, UTC-8).
    solar = solar_times(date(2026, 11, 19), 37.4636, -122.4286)
    sunrise = datetime(2026, 11, 19, 6, 54, tzinfo=LA)
    sunset = datetime(2026, 11, 19, 16, 56, tzinfo=LA)
    assert abs((solar.sunrise - sunrise).total_seconds()) <= 60
    assert abs((solar.sunset - sunset).total_seconds()) <= 60
    assert solar.sunrise.tzinfo is not None

    # USNO one-day sample in DATA_SOURCES.md for Pillar Point, same date:
    # civil twilight 06:26 and 17:25 PST.
    pillar = solar_times(date(2026, 11, 19), 37.5025, -122.4822)
    dawn = datetime(2026, 11, 19, 6, 26, tzinfo=LA)
    dusk = datetime(2026, 11, 19, 17, 25, tzinfo=LA)
    assert abs((pillar.civil_dawn - dawn).total_seconds()) <= 90
    assert abs((pillar.civil_dusk - dusk).total_seconds()) <= 90


def test_moon_phase_epoch_and_range():
    phase = moon_phase(datetime(2000, 1, 6, 18, 14, tzinfo=UTC))
    assert phase < 0.02 or phase > 0.98
    later = moon_phase(datetime(2026, 11, 21, 20, tzinfo=UTC))
    assert 0.0 <= later < 1.0


def test_minus_tide_window_crosses_local_midnight():
    samples = [
        _tide(datetime(2026, 11, 19, 6, 0, tzinfo=UTC), -0.2),
        _tide(datetime(2026, 11, 19, 7, 30, tzinfo=UTC), -1.4),
        _tide(datetime(2026, 11, 19, 9, 0, tzinfo=UTC), -0.3),
        _tide(datetime(2026, 11, 19, 10, 30, tzinfo=UTC), 0.8),
    ]
    windows = find_clamming_windows(samples, threshold_ft_mllw=0.0, clip_daylight=False)
    assert len(windows) == 1
    window = windows[0]
    assert window.start.tzinfo is not None
    assert window.start.date() != window.end.date()
    assert window.extremum_value == pytest.approx(-1.4)
    assert window.duration_hours > 0
    assert window.rank == 1


def test_no_qualifying_tide_returns_empty():
    samples = [
        _tide(aware(2026, 11, 21, 8), 1.0),
        _tide(aware(2026, 11, 21, 10), 2.0),
        _tide(aware(2026, 11, 21, 12), 3.0),
    ]
    assert find_clamming_windows(samples, threshold_ft_mllw=0.0) == []


def test_daylight_clip_drops_night_and_trims_evening():
    night = [
        _tide(aware(2026, 11, 21, 22), 0.4),
        _tide(aware(2026, 11, 21, 22, 30), -1.0),
        _tide(aware(2026, 11, 21, 23), 0.4),
    ]
    clipped = find_clamming_windows(
        night,
        threshold_ft_mllw=0.0,
        latitude=HMB_LAT,
        longitude=HMB_LON,
        clip_daylight=True,
    )
    assert clipped == []

    evening = [
        _tide(aware(2026, 11, 21, 16), 0.2),
        _tide(aware(2026, 11, 21, 16, 30), -0.8),
        _tide(aware(2026, 11, 21, 19), -0.2),
        _tide(aware(2026, 11, 21, 19, 30), 0.6),
    ]
    trimmed = find_clamming_windows(
        evening,
        threshold_ft_mllw=0.0,
        latitude=HMB_LAT,
        longitude=HMB_LON,
        clip_daylight=True,
    )
    assert len(trimmed) == 1
    assert trimmed[0].end.hour < 19
    assert trimmed[0].start < trimmed[0].end


def test_slack_and_moderate_current_windows():
    start = aware(2026, 11, 21, 9)
    samples = []
    speeds = [2.0, 0.4, -0.2, -1.0, -2.0, -0.3, 0.2]
    for offset, speed in enumerate(speeds):
        samples.append(CurrentSample(time=start + timedelta(hours=offset), velocity_kt=speed))
    windows = find_crabbing_windows(samples, slack_max_kt=0.5, moderate_max_kt=1.5)
    kinds = {window.kind for window in windows}
    assert "slack" in kinds
    assert "moderate_current" in kinds
    assert windows[0].rank == 1
    assert windows[0].score >= windows[-1].score


def test_best_clamming_label_is_local_and_ranked():
    saturday = aware(2026, 11, 21, 8)
    hours = []
    for hour in range(7, 12):
        moment = aware(2026, 11, 21, hour)
        height = -1.0 if hour in (8, 9, 10) else 1.2
        hours.append(make_hour(moment, tide_height_ft_mllw=height))
    grid = SpotFeatureGrid(
        spot_id="half_moon_bay",
        hours=hours,
        bloom_region="outer_coast",
        chlorophyll=make_chl(1.5),
    )
    tides = [
        _tide(aware(2026, 11, 21, 7, 50), 0.5),
        _tide(aware(2026, 11, 21, 8), -1.0),
        _tide(aware(2026, 11, 21, 10), -0.8),
        _tide(aware(2026, 11, 21, 10, 10), 0.5),
    ]
    ranked = best_windows(
        grid,
        "clamming",
        latitude=HMB_LAT,
        longitude=HMB_LON,
        as_of=aware(2026, 11, 20, 12),
        horizon_hours=72,
        tides=tides,
    )
    assert ranked
    best = ranked[0]
    assert best.eligible is True
    assert best.label.startswith("Best clamming: Sat ")
    assert "minus tide" in best.label
    assert best.start.tzinfo == LA or best.start.tzname() in {"PST", "PDT"}
    assert best.start.hour in (7, 8)
    assert "tide" in (best.summary or "")
    assert any(factor.name == "moon" and factor.source == "offline_lunar" for factor in best.factors)
    for factor in best.factors:
        assert factor.verdict is not None
        assert factor.observed_at is None or factor.observed_at.tzinfo is not None


def test_horizon_must_be_48_to_72():
    grid = make_grid(saturday_noon())
    with pytest.raises(ValueError):
        best_windows(grid, "clamming", latitude=HMB_LAT, longitude=HMB_LON, as_of=saturday_noon(), horizon_hours=24)


def saturday_noon():
    return aware(2026, 11, 21, 12)


def _two_hours(spot_id: str, start: datetime) -> SpotFeatureGrid:
    return SpotFeatureGrid(
        spot_id=spot_id,
        hours=[make_hour(start), make_hour(start + timedelta(hours=1))],
        bloom_region="outer_coast",
        chlorophyll=make_chl(1.2),
    )


def test_region_thresholds_match_citations():
    rules = load_region_rules()
    assert rules["bloom_regions"]["outer_coast"]["bloom_above_mg_m3"] == 5.0
    bay = rules["bloom_regions"]["sf_bay"]
    assert bay["protective_max_mg_m3"] == 13.0
    assert bay["at_risk_low_mg_m3"] == 25.0
    assert bay["at_risk_high_mg_m3"] == 40.0
    crab = get_scorer("crabbing").config
    assert crab["season"]["open"] == "2026-11-07"
    assert crab["gear"]["trap"]["boundary"] == "2027-01-01"
    assert crab["gear"]["hoop_net"]["status"] == "allowed"
    assert "2 hours" in crab["gear"]["hoop_net"]["note"]
    assert "wording conflict" in crab["gear"]["loop_trap"]["caveat"].lower()


def test_bloom_flag_carries_observation_time_and_unknown_is_not_clear():
    grid = make_grid(saturday_noon())
    flag = bloom_status(grid, get_scorer("clamming").config)
    assert flag.bloom is False
    assert flag.cannot_confirm is False
    assert flag.observed_at is not None
    assert flag.chl_mg_m3 == pytest.approx(2.0)

    grid.chlorophyll = make_chl(9.0)
    hot = bloom_status(grid, get_scorer("clamming").config)
    assert hot.bloom is True
    assert hot.observed_at is not None

    grid.chlorophyll = make_chl(1.0, status=SourceStatus.stale)
    stale = bloom_status(grid, get_scorer("clamming").config)
    assert stale.bloom is None
    assert stale.cannot_confirm is True
    assert stale.observed_at is not None


def test_haversine_one_degree_and_rank_order():
    distance = haversine_miles(0.0, 0.0, 1.0, 0.0)
    expected = 3958.7613 * math.pi / 180.0
    assert distance == pytest.approx(expected, rel=1e-6)

    near = Spot(id="near", name="Near", lat=37.50, lon=-122.48, activities=[Activity.clamming])
    far = Spot(id="far", name="Far", lat=37.90, lon=-122.48, activities=[Activity.clamming])
    blocked = Spot(id="blocked", name="Blocked", lat=37.51, lon=-122.48, activities=[Activity.clamming])
    start = saturday_noon()
    end = start + timedelta(hours=3)
    good = _two_hours("near", start)
    far_grid = _two_hours("far", start)
    bad = _two_hours("blocked", start)
    bad.chlorophyll = None
    result = rank_spots(
        37.50,
        -122.48,
        Activity.clamming,
        start,
        end,
        [far, blocked, near],
        {"near": good, "far": far_grid, "blocked": bad},
    )
    assert [spot.spot_id for spot in result.valid] == ["near", "far"]
    assert result.valid[0].distance_mi < result.valid[1].distance_mi
    rejected = next(spot for spot in result.rejected if spot.spot_id == "blocked")
    assert rejected.valid is False
    assert rejected.cannot_confirm is True
