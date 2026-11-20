"""Regressions for REVIEW_PR3 items 3, 4, and 5."""

from datetime import timedelta

from backend.models.common import SourceStatus
from backend.scorers import get_scorer
from tests.conftest import HMB_LAT, HMB_LON, all_ok, aware, make_grid

NOON = aware(2026, 11, 21, 12, 0)


def _gate(window, name):
    return next(gate for gate in window.gates if gate.name == name)


def _score(activity, grid, **kwargs):
    start = grid.hours[0].hour
    return get_scorer(activity).score_window(
        grid,
        start,
        start + timedelta(hours=1),
        lat=HMB_LAT,
        lon=HMB_LON,
        **kwargs,
    )


def test_swimming_blocks_surf_above_configured_max_and_missing_waves():
    heavy = _score("swimming", make_grid(NOON, wave_height_m=4.0, active_alerts=[]))
    surf = _gate(heavy, "surf_height")
    assert surf.passed is False
    assert surf.cannot_confirm is False
    assert heavy.eligible is False

    at_limit = _score("swimming", make_grid(NOON, wave_height_m=1.5))
    assert _gate(at_limit, "surf_height").passed is True

    missing = _score("swimming", make_grid(NOON, wave_height_m=None))
    assert _gate(missing, "surf_height").cannot_confirm is True
    assert missing.eligible is False


def test_sailing_blocks_gusts_above_configured_max_and_missing_gusts():
    gusty = _score("sailing", make_grid(NOON, wind_speed_kt=14.0, wind_gust_kt=45.0))
    gust = _gate(gusty, "gust_limit")
    assert gust.passed is False
    assert gust.cannot_confirm is False
    assert gusty.eligible is False

    at_limit = _score("sailing", make_grid(NOON, wind_speed_kt=14.0, wind_gust_kt=25.0))
    assert _gate(at_limit, "gust_limit").passed is True

    missing = _score("sailing", make_grid(NOON, wind_gust_kt=None))
    assert _gate(missing, "gust_limit").cannot_confirm is True
    assert missing.eligible is False


def test_dungeness_ban_uses_spot_flag_not_bloom_region():
    spoofed = make_grid(NOON, spot_id="crissy_field", region="outer_coast")
    banned = _score("crabbing", spoofed, gear="hoop_net")
    gate = _gate(banned, "dungeness_water")
    assert gate.passed is False
    assert gate.cannot_confirm is False
    assert banned.eligible is False

    ocean = make_grid(NOON, spot_id="pillar_point_harbor", region="sf_bay")
    allowed = _score("crabbing", ocean, gear="hoop_net")
    assert _gate(allowed, "dungeness_water").passed is True

    unknown = make_grid(NOON, spot_id="not_a_configured_spot", region="outer_coast")
    unconfirmed = _score("crabbing", unknown, gear="hoop_net")
    assert _gate(unconfirmed, "dungeness_water").cannot_confirm is True
    assert unconfirmed.eligible is False


def test_shellfish_gate_needs_explicit_false_boolean():
    clear = _score("clamming", make_grid(NOON, active_alerts=["cdph_closure=false"]))
    assert _gate(clear, "no_biotoxin_closure").passed is True

    alias = _score("clamming", make_grid(NOON, active_alerts=["any_region_advisory=false"]))
    assert _gate(alias, "no_biotoxin_closure").passed is True

    closed = _score("clamming", make_grid(NOON, active_alerts=["cdph_closure=true"]))
    assert _gate(closed, "no_biotoxin_closure").passed is False
    assert _gate(closed, "no_biotoxin_closure").cannot_confirm is False

    empty = _score("clamming", make_grid(NOON, active_alerts=[]))
    assert _gate(empty, "no_biotoxin_closure").cannot_confirm is True
    assert empty.eligible is False

    county = _score("clamming", make_grid(NOON, active_alerts=["San Mateo County"]))
    assert _gate(county, "no_biotoxin_closure").cannot_confirm is True
    assert county.eligible is False

    stale = all_ok(alerts_shellfish=SourceStatus.stale)
    stale_clear = _score(
        "clamming",
        make_grid(NOON, active_alerts=["cdph_closure=false"], source_statuses=stale),
    )
    assert _gate(stale_clear, "no_biotoxin_closure").cannot_confirm is True
