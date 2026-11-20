"""Gate, confidence, unit, and citation tests for every activity scorer."""

from __future__ import annotations

import ast
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.features.units import fahrenheit_to_celsius, meters_to_feet
from backend.models.common import Confidence, GateResult, SourceStatus
from backend.models.scoring import ScoredWindow
from backend.scorers import get_scorer
from backend.scorers.rules import ScorerConfigError
from tests.conftest import HMB_LAT, HMB_LON, UTC, all_ok, aware, make_chl, make_grid, make_hour

NOON = aware(2026, 11, 21, 12, 0)


def _score(activity, grid=None, **kwargs):
    grid = grid or make_grid(NOON)
    start = grid.hours[0].hour if grid.hours else NOON
    return get_scorer(activity).score_window(
        grid,
        start,
        start + timedelta(hours=1),
        lat=HMB_LAT,
        lon=HMB_LON,
        **kwargs,
    )


def _gate(window, name):
    return next(gate for gate in window.gates if gate.name == name)


def test_eligible_defaults_false():
    window = ScoredWindow(
        spot_id="s",
        start=NOON,
        end=NOON + timedelta(hours=1),
        score=0,
        confidence=Confidence(value=1),
    )
    assert window.eligible is False


def test_gate_result_forbids_passed_and_cannot_confirm():
    with pytest.raises(ValidationError):
        GateResult(name="g", passed=True, cannot_confirm=True, reason="no")


def test_malformed_rule_rejected_at_load():
    config = get_scorer("clamming").config
    broken = dict(config)
    broken["gates"] = [dict(broken["gates"][0], rule="tide_height_ft_mllw <=> 0")]
    with pytest.raises(ScorerConfigError):
        get_scorer("clamming", config=broken)
    unknown = dict(config)
    unknown["gates"] = [dict(unknown["gates"][0], rule="not_a_real_field == true")]
    with pytest.raises(ScorerConfigError):
        get_scorer("clamming", config=unknown)


def test_naive_window_is_rejected():
    grid = make_grid(NOON)
    with pytest.raises(ValueError):
        get_scorer("clamming").score_window(grid, datetime(2026, 11, 21, 12), datetime(2026, 11, 21, 13))


@pytest.mark.parametrize(
    "activity, gear",
    [("clamming", None), ("crabbing", "hoop_net"), ("swimming", None), ("sailing", None)],
)
def test_happy_path_passes_every_gate(activity, gear):
    window = _score(activity, gear=gear)
    assert window.eligible is True
    assert window.factors
    assert all(gate.passed and not gate.cannot_confirm for gate in window.gates)
    assert "Recommended" not in (window.summary or "")
    assert "safe" not in (window.summary or "").lower()
    assert window.start.tzinfo is not None
    assert window.start.utcoffset() is not None


def test_clamming_gates_fail_on_fresh_bad_values():
    high = _score("clamming", make_grid(NOON, tide_height_ft_mllw=0.4))
    assert _gate(high, "minus_tide").passed is False
    assert _gate(high, "minus_tide").cannot_confirm is False
    assert high.eligible is False

    closed = _score("clamming", make_grid(NOON, active_alerts=["CDPH shellfish biotoxin closure"]))
    assert _gate(closed, "no_biotoxin_closure").passed is False
    assert any(factor.verdict and factor.verdict.value == "blocked" for factor in closed.factors)
    assert any("CDPH biotoxin quarantine" in (factor.note or "") for factor in closed.factors)
    assert "CDPH biotoxin quarantine" in (closed.summary or "")
    assert "no advisories" not in (closed.summary or "")

    bloom = make_grid(NOON)
    bloom.chlorophyll = make_chl(6.0)
    bloomed = _score("clamming", bloom)
    assert _gate(bloomed, "no_bloom").passed is False
    assert bloomed.eligible is False


def test_clamming_thresholds_and_units():
    exact = _score("clamming", make_grid(NOON, tide_height_ft_mllw=0.0))
    assert _gate(exact, "minus_tide").passed is True
    above = _score("clamming", make_grid(NOON, tide_height_ft_mllw=0.01))
    assert _gate(above, "minus_tide").passed is False
    night = aware(2026, 11, 21, 3, 0)
    dark = _score("clamming", make_grid(night))
    assert _gate(dark, "daylight").passed is False
    assert dark.eligible is False


def test_missing_and_stale_never_pass_and_confidence_names_them():
    missing = _score("clamming", make_grid(NOON, tide_height_ft_mllw=None))
    gate = _gate(missing, "minus_tide")
    assert gate.passed is False and gate.cannot_confirm is True
    assert missing.eligible is False
    assert any("tide_height_ft_mllw" in note for note in missing.confidence.notes)
    assert missing.confidence.value < 1

    stale_status = all_ok(coops_tides=SourceStatus.stale)
    stale = _score("clamming", make_grid(NOON, source_statuses=stale_status))
    stale_gate = _gate(stale, "minus_tide")
    assert stale_gate.passed is False and stale_gate.cannot_confirm is True
    assert stale.eligible is False
    assert any("coops_tides" in note and "stale" in note for note in stale.confidence.notes)
    assert stale.confidence.value == pytest.approx(0.8)
    assert "safe" not in (stale.summary or "").lower()

    sentinel = _score("clamming", make_grid(NOON, tide_height_ft_mllw=999))
    assert _gate(sentinel, "minus_tide").cannot_confirm is True


def test_output_cites_only_input_measurements():
    moment = NOON
    grid = make_grid(moment, tide_height_ft_mllw=-1.37, wind_speed_kt=12.25, sst_c=17.65)
    window = _score("clamming", grid)
    inputs = {-1.37, 12.25, 17.65, 0.4, 0.2, 14.0, 2.0, 2.0}
    for gate in window.gates:
        if not gate.evidence or not gate.evidence.startswith("cited:"):
            continue
        payload = json.loads(gate.evidence[len("cited:") :])
        for item in payload:
            value = item.get("value")
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            if item.get("name") != "moon_phase":
                assert any(abs(float(value) - known) < 1e-9 for known in inputs)
    tide = next(factor for factor in window.factors if factor.name == "tide")
    assert tide.value == pytest.approx(-1.37)
    assert tide.unit == "ft MLLW"
    assert tide.verdict is not None
    assert tide.source == "coops_tides"
    assert tide.observed_at is not None and tide.observed_at.tzinfo is not None
    assert tide.age_minutes is not None


def test_factor_age_uses_as_of():
    window = _score("clamming", as_of=NOON + timedelta(hours=2))
    tide = next(factor for factor in window.factors if factor.name == "tide")
    assert tide.age_minutes == pytest.approx(120.0, abs=1.0)


def test_summary_lists_verdicts_and_clear_advisories():
    window = _score("clamming")
    assert window.summary is not None
    assert "tide -1.2 ft (good)" in window.summary
    assert "no advisories" in window.summary
    assert any(factor.name == "moon" for factor in window.factors)


def test_crabbing_gear_season_and_bay():
    ok = _score("crabbing", gear="hoop_net")
    gear_gate = _gate(ok, "gear_allowed")
    assert gear_gate.passed is True
    assert "2 hours" in gear_gate.reason

    loop = _score("crabbing", gear="loop_trap")
    assert _gate(loop, "gear_allowed").passed is True
    assert "wording conflict" in _gate(loop, "gear_allowed").reason.lower()

    spear = _score("crabbing", gear="spear")
    assert _gate(spear, "gear_allowed").cannot_confirm is True
    assert spear.eligible is False

    missing_gear = _score("crabbing", gear=None)
    assert _gate(missing_gear, "gear_allowed").cannot_confirm is True

    trap = _score("crabbing", make_grid(aware(2026, 12, 15, 12)), gear="trap")
    assert _gate(trap, "gear_allowed").passed is False
    assert _gate(trap, "gear_allowed").cannot_confirm is False

    later = _score("crabbing", make_grid(aware(2027, 1, 1, 12)), gear="trap")
    assert _gate(later, "gear_allowed").cannot_confirm is True

    before = _score("crabbing", make_grid(aware(2026, 11, 6, 12)), gear="hoop_net")
    assert _gate(before, "season_open").passed is False
    opening = _score("crabbing", make_grid(aware(2026, 11, 7, 8)), gear="hoop_net")
    assert _gate(opening, "season_open").passed is True

    # 07:30 UTC on Nov 7 is still Nov 6 in Los Angeles.
    still_closed = make_grid(datetime(2026, 11, 7, 7, 30, tzinfo=UTC))
    closed_window = get_scorer("crabbing").score_window(
        still_closed,
        datetime(2026, 11, 7, 7, tzinfo=UTC),
        datetime(2026, 11, 7, 8, tzinfo=UTC),
        lat=HMB_LAT,
        lon=HMB_LON,
        gear="hoop_net",
    )
    assert _gate(closed_window, "season_open").passed is False

    bay = _score("crabbing", make_grid(NOON, spot_id="sf_bay", region="sf_bay"), gear="hoop_net")
    assert _gate(bay, "dungeness_water").passed is False
    assert bay.eligible is False

    bare = get_scorer("crabbing").config
    without_season = dict(bare)
    without_season.pop("season")
    unknown = get_scorer("crabbing", config=without_season).score_window(
        make_grid(NOON),
        NOON,
        NOON + timedelta(hours=1),
        lat=HMB_LAT,
        lon=HMB_LON,
        gear="hoop_net",
    )
    assert _gate(unknown, "season_open").cannot_confirm is True
    assert unknown.eligible is False


def test_crabbing_night_keeps_moon_factor():
    night = _score("crabbing", make_grid(aware(2026, 11, 21, 2)), gear="hoop_net")
    moon = next(factor for factor in night.factors if factor.name == "moon")
    assert moon.source == "offline_lunar"
    assert moon.value is not None
    assert "night" in (moon.note or "").lower()


def test_swimming_gates():
    bacteria = _score("swimming", make_grid(NOON, active_alerts=["beach bacteria advisory"]))
    assert _gate(bacteria, "no_bacteria_advisory").passed is False
    rip = _score("swimming", make_grid(NOON, active_alerts=["High Surf Advisory"]))
    assert _gate(rip, "rip_current_not_high").passed is False
    moderate = _score("swimming", make_grid(NOON, active_alerts=["rip current risk: moderate"]))
    assert _gate(moderate, "rip_current_not_high").passed is True

    cold = fahrenheit_to_celsius(60)
    shock = _score("swimming", make_grid(NOON, sst_c=cold))
    assert _gate(shock, "cold_shock").passed is False
    warmer = _score("swimming", make_grid(NOON, sst_c=cold + 0.1))
    assert _gate(warmer, "cold_shock").passed is True

    missing_sst = _score("swimming", make_grid(NOON, sst_c=None))
    assert _gate(missing_sst, "cold_shock").cannot_confirm is True
    stale = all_ok(sst=SourceStatus.stale)
    stale_swim = _score("swimming", make_grid(NOON, source_statuses=stale, sst_c=18))
    assert _gate(stale_swim, "cold_shock").cannot_confirm is True
    assert any("sst" in note and "stale" in note for note in stale_swim.confidence.notes)


def test_sailing_sca_boundaries_and_ebb():
    at_21 = _score("sailing", make_grid(NOON, wind_speed_kt=21.0, wave_height_m=0.5))
    assert _gate(at_21, "no_small_craft_advisory").passed is False
    under = _score("sailing", make_grid(NOON, wind_speed_kt=20.9, wave_height_m=0.5))
    assert _gate(under, "no_small_craft_advisory").passed is True

    ten_feet = 10 * 0.3048
    exact_seas = _score("sailing", make_grid(NOON, wind_speed_kt=10, wave_height_m=ten_feet))
    assert _gate(exact_seas, "no_small_craft_advisory").passed is True
    assert meters_to_feet(ten_feet) == pytest.approx(10.0, abs=1e-6)
    over_seas = _score("sailing", make_grid(NOON, wind_speed_kt=10, wave_height_m=ten_feet + 0.05))
    assert _gate(over_seas, "no_small_craft_advisory").passed is False

    alert = _score("sailing", make_grid(NOON, wind_speed_kt=8, active_alerts=["Small Craft Advisory"]))
    assert _gate(alert, "no_small_craft_advisory").passed is False
    storm = _score("sailing", make_grid(NOON, active_alerts=["Special Marine Warning"]))
    assert _gate(storm, "no_thunderstorm").passed is False

    stale_alerts = all_ok(nws_alerts=SourceStatus.stale)
    stale = _score("sailing", make_grid(NOON, source_statuses=stale_alerts, wind_speed_kt=8))
    assert _gate(stale, "no_small_craft_advisory").cannot_confirm is True
    assert stale.eligible is False

    ebb = _score("sailing", make_grid(NOON, current_velocity_kt=-2.0, wave_height_m=3.0, wind_speed_kt=10))
    assert _gate(ebb, "no_ebb_against_swell").passed is False
    calm_ebb = _score("sailing", make_grid(NOON, current_velocity_kt=-2.0, wave_height_m=0.5, wind_speed_kt=10))
    assert _gate(calm_ebb, "no_ebb_against_swell").passed is True

    sentinel = _score("sailing", make_grid(NOON, wind_speed_kt=999))
    assert _gate(sentinel, "no_small_craft_advisory").cannot_confirm is True


def test_bloom_regions_and_missing_satellite():
    outer = make_grid(NOON)
    outer.chlorophyll = make_chl(5.0)
    assert _gate(_score("clamming", outer), "no_bloom").passed is True
    outer.chlorophyll = make_chl(5.01)
    assert _gate(_score("clamming", outer), "no_bloom").passed is False

    bay = make_grid(NOON, spot_id="sf_bay", region="sf_bay")
    bay.chlorophyll = make_chl(13.0)
    assert _gate(_score("swimming", bay), "no_bloom").passed is True
    bay.chlorophyll = make_chl(13.1)
    failed = _score("swimming", bay)
    assert _gate(failed, "no_bloom").passed is False
    bay.chlorophyll = make_chl(30.0)
    at_risk = _score("swimming", bay)
    assert "at-risk" in _gate(at_risk, "no_bloom").reason or "above" in _gate(at_risk, "no_bloom").reason

    stale = make_grid(NOON)
    stale.chlorophyll = make_chl(1.0, status=SourceStatus.stale)
    unconfirmed = _score("clamming", stale)
    assert _gate(unconfirmed, "no_bloom").cannot_confirm is True
    assert unconfirmed.eligible is False

    unknown_region = make_grid(NOON, spot_id="unmapped", region=None)
    unknown_region.bloom_region = None
    assert _gate(_score("clamming", unknown_region), "no_bloom").cannot_confirm is True


def test_live_path_does_not_import_tests_or_mocks():
    roots = [Path("backend/scorers"), Path("backend/features"), Path("backend/config")]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text()
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    assert not name.startswith("tests")
                    assert "unittest.mock" not in name
                    assert name != "pytest"
