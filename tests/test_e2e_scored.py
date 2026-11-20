"""phase3-e2e: adapters (fixtures) -> grid -> real scorers -> windows, via orchestrator and API."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from backend import api as api_mod
from backend.adapters.coops import TidePayload, TidePoint
from backend.adapters.erddap import ChlPayload, SstPayload
from backend.adapters.ndbc import NdbcObs
from backend.grid_builder import (
    SHELLFISH_CLEAR,
    SHELLFISH_CLOSED,
    build_grid,
    ms_to_kt,
    shellfish_alert_tokens,
)
from backend.models.common import Activity, SourceStatus
from backend.models.sources import SourceResult
from backend.orchestrator import SpotFetchBundle

LA = ZoneInfo("America/Los_Angeles")
UTC = timezone.utc


def _tides(now: datetime) -> TidePayload:
    """Minus low at noon LA tomorrow (daylight), highs 6 h either side, ~12.4 h cycle."""
    low = (now.astimezone(LA) + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    pts = []
    for k in range(-4, 5):
        t = low + timedelta(hours=6.2 * k)
        is_low = k % 2 == 0
        pts.append(TidePoint(t=t.astimezone(UTC), v_ft_mllw=-0.8 if is_low else 5.0, type="L" if is_low else "H"))
    return TidePayload(station_id="9414131", product="predictions_hilo", points=pts,
                       observed_at=max(p.t for p in pts))


def _res(name: str, payload, now: datetime, observed: datetime | None, status=SourceStatus.ok):
    return SourceResult(data=payload, fetched_at=now, valid_until=now + timedelta(hours=1),
                        status=status, source_name=name, observed_at=observed)


def _results(now: datetime, *, chl_age: timedelta = timedelta(days=1), cdph=None):
    tides = _tides(now)
    out = {
        "coops_tides": _res("coops_tides", tides, now, tides.observed_at),
        "erddap_chl": _res("erddap_chl", ChlPayload(chla_mg_m3=1.2, observed_at=now - chl_age,
                                                   stale=False), now, now - chl_age),
        "erddap_sst": _res("erddap_sst", SstPayload(sst_c=14.0, observed_at=now - timedelta(hours=20),
                                                   stale=False), now, now - timedelta(hours=20)),
    }
    if cdph is not None:
        out["cdph_shellfish"] = _res("cdph_shellfish", cdph, now, now)
    return out


MAXAGES = {"erddap_chl": timedelta(days=10), "erddap_sst": timedelta(days=3),
           "cdph_shellfish": timedelta(hours=6), "ndbc_buoy": timedelta(hours=3)}


def _spot(spot_id="pillar_point_harbor"):
    return next(s for s in api_mod.region.spots if s.id == spot_id)


def _bundle(spot, results):
    return SpotFetchBundle(spot=spot, results=results, errors={})


def _gate(window, name):
    return next(g for g in window.gates if g.name == name)


# --- unit-level mapping -------------------------------------------------------------
def test_ndbc_ms_to_knots_conversion():
    assert ms_to_kt(10.0) == pytest.approx(19.44, abs=0.01)
    assert ms_to_kt(None) is None
    now = datetime.now(UTC)
    obs = NdbcObs(station_id="46026", observed_at=now - timedelta(minutes=20), wspd_ms=5.0, gst_ms=8.0, wvht_m=1.5)
    res = {"ndbc_buoy": _res("ndbc_buoy", obs, now, obs.observed_at)}
    grid = build_grid(_spot(), res, {}, now - timedelta(hours=1), now + timedelta(hours=2),
                      now=now, max_ages=MAXAGES).grid
    hour = next(h for h in grid.hours if h.wind_speed_kt is not None)
    assert hour.wind_speed_kt == pytest.approx(9.72, abs=0.01)
    assert hour.wind_gust_kt == pytest.approx(15.55, abs=0.01)
    assert hour.wave_height_m == 1.5


@pytest.mark.parametrize(
    "value, status, cannot, expected",
    [
        (False, SourceStatus.ok, False, [SHELLFISH_CLEAR]),
        (True, SourceStatus.ok, False, [SHELLFISH_CLOSED]),
        (None, SourceStatus.ok, False, []),
        ([], SourceStatus.ok, False, []),
        ("San Mateo County", SourceStatus.ok, False, []),
        ("false", SourceStatus.ok, False, []),
        (0, SourceStatus.ok, False, []),
        (False, SourceStatus.stale, False, []),
        (False, SourceStatus.ok, True, []),
        (False, SourceStatus.down, False, []),
    ],
)
def test_shellfish_tokens_only_explicit_fresh_bool(value, status, cannot, expected):
    payload = SimpleNamespace(any_region_advisory=value, cannot_confirm=cannot)
    assert shellfish_alert_tokens(payload, status) == expected
    assert shellfish_alert_tokens(None, SourceStatus.ok) == []


# --- through the orchestrator ---------------------------------------------------------
NOW = datetime(2026, 12, 5, 7, 0, tzinfo=LA).astimezone(UTC)


def _score(results, activity=Activity.clamming, spot=None, gear=None):
    orch = api_mod.orchestrator
    spot = spot or _spot()
    start, end = NOW, NOW + timedelta(hours=48)
    # fixture tides are built relative to NOW (low at noon on 2026-12-06)
    return orch.score_spot(_bundle(spot, results), activity, start, end, gear=gear, now=NOW)


@pytest.mark.parametrize(
    "bad", [None, [], "San Mateo County", "false", 0],
    ids=["none", "empty_list", "county_string", "string_false", "zero"],
)
def test_bad_cdph_inputs_give_cannot_confirm_not_eligible(bad):
    cdph = SimpleNamespace(any_region_advisory=bad, cannot_confirm=False)
    windows, _ = _score(_results(NOW, cdph=cdph))
    assert windows, "tide fixture must produce clamming windows"
    for w in windows:
        g = _gate(w, "no_biotoxin_closure")
        assert g.cannot_confirm and not g.passed
        assert w.eligible is False


def test_missing_cdph_is_cannot_confirm():
    windows, _ = _score(_results(NOW))
    assert windows and all(not w.eligible for w in windows)
    assert all(_gate(w, "no_biotoxin_closure").cannot_confirm for w in windows)


def test_explicit_cdph_advisory_blocks():
    cdph = SimpleNamespace(any_region_advisory=True, cannot_confirm=False)
    windows, _ = _score(_results(NOW, cdph=cdph))
    assert windows
    assert all(_gate(w, "no_biotoxin_closure").passed is False for w in windows)
    assert all(not _gate(w, "no_biotoxin_closure").cannot_confirm for w in windows)
    assert all(not w.eligible for w in windows)


def test_stale_chl_19_days_is_cannot_confirm():
    cdph = SimpleNamespace(any_region_advisory=False, cannot_confirm=False)
    res = _results(NOW, chl_age=timedelta(days=19), cdph=cdph)
    built = build_grid(_spot(), res, {}, NOW, NOW + timedelta(hours=24), now=NOW, max_ages=MAXAGES)
    assert built.statuses["satellite_chl"] is SourceStatus.stale
    assert built.grid.chlorophyll is not None and built.grid.chlorophyll.chl_mg_m3 is None
    windows, _ = _score(res)
    assert windows
    for w in windows:
        assert _gate(w, "no_bloom").cannot_confirm
        assert not w.eligible


def test_missing_observed_at_is_not_fresh_in_grid():
    cdph = SimpleNamespace(any_region_advisory=False, cannot_confirm=False)
    res = _results(NOW, cdph=cdph)
    res["cdph_shellfish"].observed_at = None
    built = build_grid(_spot(), res, {}, NOW, NOW + timedelta(hours=24), now=NOW, max_ages=MAXAGES)
    assert built.statuses["alerts_shellfish"] is not SourceStatus.ok
    assert all(not h.active_alerts for h in built.grid.hours)


def test_sf_bay_dungeness_ineligible_even_with_every_gate_clear():
    bay = _spot("crissy_field")
    bay_crab = bay.model_copy(update={"activities": [*bay.activities, Activity.crabbing]})
    assert bay_crab.dungeness_prohibited
    cdph = SimpleNamespace(any_region_advisory=False, cannot_confirm=False)
    windows, _ = _score(_results(NOW, cdph=cdph), Activity.crabbing, spot=bay_crab, gear="hoop_net")
    for w in windows:
        assert w.eligible is False
        assert _gate(w, "dungeness_water").passed is False


# --- through the API (no 501, real windows) ----------------------------------------------
@pytest.fixture
def fixture_fetch(monkeypatch):
    now = datetime.now(UTC)

    async def fake(spot, start, end, *, sources=None):
        return _bundle(spot, _results(now))

    monkeypatch.setattr(api_mod.orchestrator, "fetch_spot_sources", fake)


def test_api_recommend_returns_scored_windows(fixture_fetch):
    client = TestClient(api_mod.app)
    r = client.get("/recommend", params={"activity": "clamming", "spot": "pillar_point_harbor"})
    assert r.status_code == 200
    body = r.json()
    assert body["scorer"] == "activity_scorers"
    windows = body["recommendations"][0]["windows"]
    assert windows, "expected non-empty windows from fixture adapters"
    w = windows[0]
    assert w["eligible"] is False  # shellfish cannot be confirmed
    assert any(g["name"] == "no_biotoxin_closure" and g["cannot_confirm"] for g in w["gates"])
    f = w["factors"][0]
    assert {"name", "value", "unit", "verdict", "source", "observed_at", "age_minutes"} <= set(f)


def test_api_query_returns_windows_and_explanation(fixture_fetch):
    client = TestClient(api_mod.app)
    r = client.post("/query", json={"text": "Can I go clamming at Pillar Point tomorrow?"})
    assert r.status_code == 200
    body = r.json()
    assert body["scorer"] == "activity_scorers"
    assert body["recommendations"][0]["windows"]
    assert "NOT recommended" in body["explanation"]
    assert "no_biotoxin_closure" in body["explanation"]


def test_api_query_without_activity_asks_clarifying(fixture_fetch):
    client = TestClient(api_mod.app)
    r = client.post("/query", json={"text": "somewhere nice"})
    assert r.status_code == 200 and r.json()["clarifying"]
