"""Fixture tests for CO-OPS, NDBC, and NWS. No live network."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from backend.adapters.coops import CoopsCurrentAdapter, CoopsTideAdapter, user_agent as coops_ua
from backend.adapters.ndbc import NdbcAdapter, NdbcObs
from backend.adapters.nws import NwsAlertsAdapter, user_agent as nws_ua
from backend.adapters.registry import AdapterRegistry
from backend.cache.memory import MemoryTTLCache
from backend.models.common import Activity, SourceStatus
from backend.models.spots import Spot

FIXTURES = Path(__file__).parent / "fixtures"
START = datetime(2026, 11, 19, 12, tzinfo=timezone.utc)
END = datetime(2026, 11, 20, 0, tzinfo=timezone.utc)


def _spot(**kwargs) -> Spot:
    base = dict(
        id="pillar_point_harbor",
        name="Pillar Point",
        lat=37.502,
        lon=-122.487,
        activities=[Activity.clamming, Activity.crabbing, Activity.sailing],
        tide_station_id="9414131",
        current_station_id="SFB1201",
        buoy_ids=["46012", "46237"],
        nws_zone="PZZ545",
    )
    base.update(kwargs)
    return Spot(**base)


def _install_transport(monkeypatch, module: str, handler):
    transport = httpx.MockTransport(handler)
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real(*args, **kwargs)

    monkeypatch.setattr(f"{module}.httpx.AsyncClient", factory)


def test_user_agents_identify_the_project_without_an_email():
    for agent in (coops_ua(), nws_ua()):
        assert agent.startswith("TideWise/")
        assert "github.com/AarenSunny/tidewise-grokathon" in agent
        assert "@" not in agent


def test_six_minute_tides_drop_sentinels_and_keep_minus_tide():
    adapter = CoopsTideAdapter(MemoryTTLCache(), interval="6")
    raw = json.loads((FIXTURES / "coops_tides_6min.json").read_text())
    raw["_station_id"] = "9414290"
    payload = adapter._validate(raw)
    heights = [p.v_ft_mllw for p in payload.points]
    assert heights == [4.10, 4.02, -1.25]
    assert all(p.type is None for p in payload.points)
    assert payload.units == "ft"
    assert payload.datum == "MLLW"
    assert payload.product == "predictions_6"
    assert payload.observed_at == datetime(2026, 11, 19, 15, 18, tzinfo=timezone.utc)
    assert payload.observed_at.tzinfo is not None
    assert payload.dropped_points == 1


def test_hilo_rejects_rows_without_high_or_low_type():
    adapter = CoopsTideAdapter(MemoryTTLCache(), interval="hilo")
    raw = {
        "_station_id": "9414131",
        "predictions": [
            {"t": "2026-11-19 08:12", "v": "1.2", "type": "L"},
            {"t": "2026-11-19 15:00", "v": "5.0"},
            {"t": "2026-11-19 21:00", "v": "20.0", "type": "H"},
        ],
    }
    payload = adapter._validate(raw)
    assert len(payload.points) == 1
    assert payload.points[0].type == "L"
    assert payload.points[0].v_ft_mllw == 1.2


def test_currents_use_knots_preserve_ebb_sign_and_do_not_invent_slack():
    adapter = CoopsCurrentAdapter(MemoryTTLCache())
    raw = json.loads((FIXTURES / "coops_currents_ok.json").read_text())
    raw["_station_id"] = "SFB1201"
    payload = adapter._validate(raw)
    assert payload.units == "knots"
    assert payload.bin_id == "26"
    assert [(p.type, p.velocity_kt) for p in payload.points] == [
        ("flood", 2.16),
        ("slack", 0.0),
        ("ebb", -2.64),
    ]
    assert payload.observed_at.tzinfo is not None
    assert payload.depth_ft == 19


def test_currents_reject_unconfirmed_or_non_knot_units():
    adapter = CoopsCurrentAdapter(MemoryTTLCache())
    raw = json.loads((FIXTURES / "coops_currents_ok.json").read_text())
    raw["_station_id"] = "SFB1201"
    raw["current_predictions"]["units"] = "cm/s"
    with pytest.raises(Exception, match="not knots"):
        adapter._validate(raw)
    raw["current_predictions"].pop("units")
    with pytest.raises(Exception, match="units unconfirmed"):
        adapter._validate(raw)


@pytest.mark.asyncio
async def test_missing_current_station_fetch_is_down():
    adapter = CoopsCurrentAdapter(MemoryTTLCache())
    result = await adapter.fetch(_spot(current_station_id=None), START, END)
    assert result.status == SourceStatus.down
    assert result.data is None


@pytest.mark.asyncio
async def test_coops_requests_gmt_mllw_english_and_does_not_retry_400(monkeypatch):
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(400, json={"error": {"message": "bad station"}})

    _install_transport(monkeypatch, "backend.adapters.coops", handler)
    adapter = CoopsTideAdapter(MemoryTTLCache())
    adapter.backoff_base_s = 0
    adapter.max_retries = 3
    result = await adapter.fetch(_spot(), START, END)
    assert result.status == SourceStatus.down
    assert len(calls) == 1
    params = dict(calls[0].url.params)
    assert params["time_zone"] == "gmt"
    assert params["datum"] == "MLLW"
    assert params["units"] == "english"
    assert params["interval"] == "hilo"
    assert params["station"] == "9414131"
    assert calls[0].headers["user-agent"].startswith("TideWise/")
    assert "@" not in calls[0].headers["user-agent"]
    joined = " ".join(result.notes).lower()
    assert "http://" not in joined and "https://" not in joined


@pytest.mark.asyncio
async def test_coops_retries_503_then_parses(monkeypatch):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            return httpx.Response(503, text="unavailable")
        return httpx.Response(
            200,
            json={
                "predictions": [{"t": "2026-11-19 18:00", "v": "5.5", "type": "H"}],
            },
        )

    _install_transport(monkeypatch, "backend.adapters.coops", handler)
    adapter = CoopsTideAdapter(MemoryTTLCache())
    adapter.backoff_base_s = 0
    result = await adapter.fetch(_spot(), START, END)
    assert calls["n"] == 2
    assert result.status == SourceStatus.ok
    assert result.data.points[0].v_ft_mllw == 5.5
    assert result.observed_at == datetime(2026, 11, 19, 18, tzinfo=timezone.utc)


def test_ndbc_converts_wind_to_knots_and_keeps_partial_mm():
    adapter = NdbcAdapter(MemoryTTLCache())
    text = (FIXTURES / "ndbc_wind_mm.txt").read_text()
    obs = adapter._validate({"station_id": "46237", "text": text})
    assert isinstance(obs, NdbcObs)
    assert obs.wdir_deg is None
    assert obs.wspd_kt is None
    assert obs.gst_kt is None
    assert obs.wvht_m == 2.1
    assert obs.wtmp_c == 14.2
    assert obs.observed_at.tzinfo is not None


def test_ndbc_direction_99_is_real_and_999_is_missing():
    adapter = NdbcAdapter(MemoryTTLCache())
    text = (
        "#YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP DEWP VIS PTDY TIDE\n"
        "#yr mo dy hr mn degT m/s m/s m sec sec degT hPa degC degC degC nmi hPa ft\n"
        "2026 11 19 22 30 99 99.0 1.0 1.5 MM MM MM MM MM 13.0 MM MM MM MM\n"
    )
    obs = adapter._validate({"station_id": "46026", "text": text})
    assert obs.wdir_deg == 99.0
    assert obs.wspd_kt is None
    assert obs.wspd_ms is None
    text_999 = text.replace(" 99 99.0 ", " 999 4.0 ", 1)
    obs_999 = adapter._validate({"station_id": "46026", "text": text_999})
    assert obs_999.wdir_deg is None
    assert obs_999.wspd_ms == 4.0
    assert obs_999.wspd_kt == pytest.approx(4.0 * 1.94384)


def test_ndbc_discards_gust_below_wind_and_rejects_all_missing():
    adapter = NdbcAdapter(MemoryTTLCache())
    text = (
        "#YY MM DD hh mm WDIR WSPD GST WVHT DPD APD MWD PRES ATMP WTMP DEWP VIS PTDY TIDE\n"
        "#yr mo dy hr mn degT m/s m/s m sec sec degT hPa degC degC degC nmi hPa ft\n"
        "2026 11 19 22 30 300 10.0 1.0 1.2 MM MM MM MM MM 12.0 MM MM MM MM\n"
    )
    obs = adapter._validate({"station_id": "46026", "text": text})
    assert obs.wspd_ms == 10.0
    assert obs.gst_ms is None
    assert any("gust_below_wind" in note for note in obs.notes)
    empty = text.replace("300 10.0 1.0 1.2", "MM MM MM MM", 1).replace("12.0", "MM", 1)
    with pytest.raises(Exception, match="no usable"):
        adapter._validate({"station_id": "46026", "text": empty})


def test_ndbc_stale_file_keeps_its_timestamp():
    adapter = NdbcAdapter(MemoryTTLCache())
    text = (FIXTURES / "ndbc_stale.txt").read_text()
    obs = adapter._validate({"station_id": "46239", "text": text})
    assert obs.observed_at == datetime(2026, 10, 25, 18, 0, tzinfo=timezone.utc)
    assert obs.stale is True
    assert obs.wspd_kt == pytest.approx(8.0 * 1.94384)


@pytest.mark.asyncio
async def test_ndbc_falls_back_to_next_listed_buoy_when_primary_is_empty(monkeypatch):
    good = (FIXTURES / "ndbc_sample.txt").read_text()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/46012.txt"):
            return httpx.Response(404, text="missing")
        assert request.url.path.endswith("/46237.txt")
        assert request.headers["user-agent"].startswith("TideWise/")
        return httpx.Response(200, text=good)

    _install_transport(monkeypatch, "backend.adapters.ndbc", handler)
    adapter = NdbcAdapter(MemoryTTLCache())
    raw = await adapter._fetch_live(_spot(), START, END)
    assert raw["station_id"] == "46237"
    assert raw["_fallback_used"] == "buoy:46237"
    obs = adapter._validate(raw)
    assert obs.fallback_used == "buoy:46237"
    assert obs.wtmp_c == 18.8


@pytest.mark.asyncio
async def test_ndbc_missing_buoy_ids_is_down():
    adapter = NdbcAdapter(MemoryTTLCache())
    result = await adapter.fetch(_spot(buoy_ids=[]), START, END)
    assert result.status == SourceStatus.down
    assert result.data is None


def _alert(event: str, **props) -> dict:
    body = {
        "id": props.pop("id", event),
        "event": event,
        "status": props.pop("status", "Actual"),
        "messageType": props.pop("messageType", "Alert"),
        "severity": "Minor",
        "sent": "2026-11-19T18:00:00+00:00",
        "onset": "2026-11-19T18:00:00+00:00",
        "ends": "2026-11-20T06:00:00+00:00",
        "headline": props.pop("headline", event),
        "geocode": {"UGC": ["PZZ545"]},
    }
    body.update(props)
    return {"type": "Feature", "properties": body}


def _nws_raw(point_features, zone_features=None, zone="PZZ545", updated="2026-11-19T22:00:00+00:00"):
    point = {"type": "FeatureCollection", "features": point_features, "updated": updated}
    raw = {
        "point": point,
        "marine_zone": zone,
        "_window_start": START.isoformat(),
        "_window_end": END.isoformat(),
    }
    if zone is not None:
        raw["zone"] = {
            "type": "FeatureCollection",
            "features": [] if zone_features is None else zone_features,
            "updated": updated,
        }
    return raw


def test_nws_classifies_small_craft_gale_and_beach_hazards():
    adapter = NwsAlertsAdapter(MemoryTTLCache())
    raw = _nws_raw(
        [_alert("Beach Hazards Statement", id="beach-1", headline="High surf and rip currents")],
        [_alert("Small Craft Advisory", id="sca-1"), _alert("Gale Warning", id="gale-1")],
    )
    payload = adapter._validate(raw)
    assert payload.small_craft_advisory is True
    assert payload.gale_warning is True
    assert payload.beach_hazard is True
    assert payload.any_hazard is True
    assert payload.marine_zone_checked is True
    assert payload.observed_at == datetime(2026, 11, 19, 22, tzinfo=timezone.utc)
    assert "Small Craft Advisory" in payload.active_event_names
    assert "Beach Hazards Statement" in payload.active_event_names


def test_nws_empty_feature_collection_is_a_confirmed_all_clear():
    adapter = NwsAlertsAdapter(MemoryTTLCache())
    payload = adapter._validate(_nws_raw([]))
    assert payload.alerts == []
    assert payload.small_craft_advisory is False
    assert payload.gale_warning is False
    assert payload.beach_hazard is False
    assert payload.any_hazard is False
    assert payload.observed_at.tzinfo is not None


def test_nws_without_a_marine_zone_cannot_confirm_small_craft():
    adapter = NwsAlertsAdapter(MemoryTTLCache())
    raw = _nws_raw([], zone=None)
    payload = adapter._validate(raw)
    assert payload.marine_zone_checked is False
    assert payload.small_craft_advisory is None
    assert payload.gale_warning is None
    assert payload.beach_hazard is False
    assert payload.any_hazard is None


def test_nws_test_and_cancelled_alerts_are_not_hazards():
    adapter = NwsAlertsAdapter(MemoryTTLCache())
    raw = _nws_raw(
        [],
        [
            _alert("Small Craft Advisory", id="test-1", status="Test"),
            _alert("Gale Warning", id="cancel-1", messageType="Cancel"),
        ],
    )
    payload = adapter._validate(raw)
    assert payload.small_craft_advisory is False
    assert payload.gale_warning is False


def test_nws_alert_without_an_end_time_cannot_confirm():
    adapter = NwsAlertsAdapter(MemoryTTLCache())
    raw = _nws_raw([], [_alert("Small Craft Advisory", id="open-1", ends=None)])
    payload = adapter._validate(raw)
    assert payload.small_craft_advisory is None
    assert payload.any_hazard is None


def test_nws_malformed_collection_is_rejected():
    adapter = NwsAlertsAdapter(MemoryTTLCache())
    raw = _nws_raw([])
    raw["point"] = {"type": "FeatureCollection", "updated": "2026-11-19T22:00:00+00:00"}
    with pytest.raises(Exception, match="FeatureCollection"):
        adapter._validate(raw)
    raw = _nws_raw([])
    raw["point"]["updated"] = None
    raw["zone"]["updated"] = None
    with pytest.raises(Exception, match="observed_at"):
        adapter._validate(raw)


@pytest.mark.asyncio
async def test_nws_sends_user_agent_and_queries_point_and_zone(monkeypatch):
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [],
                "updated": datetime.now(timezone.utc).isoformat(),
            },
        )

    _install_transport(monkeypatch, "backend.adapters.nws", handler)
    adapter = NwsAlertsAdapter(MemoryTTLCache())
    result = await adapter.fetch(_spot(), START, END)
    assert result.status == SourceStatus.ok
    assert result.data.small_craft_advisory is False
    assert result.observed_at is not None
    assert result.observed_at.tzinfo is not None
    assert len(seen) == 2
    queries = [dict(req.url.params) for req in seen]
    assert {"point": "37.5020,-122.4870"} in queries
    assert {"zone": "PZZ545"} in queries
    for req in seen:
        assert req.headers["user-agent"].startswith("TideWise/")
        assert "@" not in req.headers["user-agent"]
        assert "geo+json" in req.headers["accept"]


@pytest.mark.asyncio
async def test_nws_zone_failure_does_not_become_an_all_clear(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if "zone" in dict(request.url.params):
            return httpx.Response(503, text="down")
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [],
                "updated": datetime.now(timezone.utc).isoformat(),
            },
        )

    _install_transport(monkeypatch, "backend.adapters.nws", handler)
    adapter = NwsAlertsAdapter(MemoryTTLCache())
    adapter.backoff_base_s = 0
    adapter.max_retries = 2
    result = await adapter.fetch(_spot(), START, END)
    assert result.status == SourceStatus.down
    assert result.data is None


@pytest.mark.asyncio
async def test_coops_rejects_a_mismatched_station_id(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "metadata": {"id": "9414290"},
                "predictions": [{"t": "2026-11-19 18:00", "v": "1.0", "type": "L"}],
            },
        )

    _install_transport(monkeypatch, "backend.adapters.coops", handler)
    adapter = CoopsTideAdapter(MemoryTTLCache())
    result = await adapter.fetch(_spot(tide_station_id="9414131"), START, END)
    assert result.status == SourceStatus.down
    assert result.data is None


@pytest.mark.asyncio
async def test_nws_refuses_pagination_that_leaves_the_api_host(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [],
                "updated": datetime.now(timezone.utc).isoformat(),
                "pagination": {"next": "https://evil.example/alerts"},
            },
        )

    _install_transport(monkeypatch, "backend.adapters.nws", handler)
    adapter = NwsAlertsAdapter(MemoryTTLCache())
    adapter.backoff_base_s = 0
    result = await adapter.fetch(_spot(), START, END)
    assert result.status == SourceStatus.down
    assert result.data is None


@pytest.mark.asyncio
async def test_currents_requests_the_window_and_keeps_slack_zero(monkeypatch):
    """P3-4: real cp shape, Velocity_Major 0 is slack, begin/end not date=today."""
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(dict(request.url.params))
        body = json.loads((FIXTURES / "coops_currents_ok.json").read_text())
        return httpx.Response(200, json=body)

    _install_transport(monkeypatch, "backend.adapters.coops", handler)
    adapter = CoopsCurrentAdapter(MemoryTTLCache())
    result = await adapter.fetch(_spot(), START, END)
    assert "date" not in seen
    assert seen["begin_date"] == "20261119"
    assert seen["end_date"] == "20261119"
    assert seen["time_zone"] == "gmt"
    assert seen["units"] == "english"
    assert result.status == SourceStatus.ok
    slacks = [p for p in result.data.points if p.type == "slack"]
    assert slacks
    assert all(p.velocity_kt == 0.0 for p in slacks)


def test_currents_reject_series_outside_the_requested_window():
    adapter = CoopsCurrentAdapter(MemoryTTLCache())
    raw = json.loads((FIXTURES / "coops_currents_ok.json").read_text())
    raw["_station_id"] = "SFB1201"
    raw["_window_start"] = "2026-11-21T00:00:00+00:00"
    raw["_window_end"] = "2026-11-22T00:00:00+00:00"
    with pytest.raises(Exception, match="do not cover"):
        adapter._validate(raw)


@pytest.mark.asyncio
async def test_ndbc_missing_buoy_does_not_reuse_another_station_cache():
    """P3-5: no buoy_ids must not collide with station 46026."""
    cache = MemoryTTLCache()
    adapter = NdbcAdapter(cache)
    text = (FIXTURES / "ndbc_sample.txt").read_text()

    async def fake_live(spot, start, end):
        return {"station_id": spot.buoy_ids[0], "text": text}

    adapter._fetch_live = fake_live  # type: ignore[method-assign]
    buoy = _spot(id="pillar_point_harbor", buoy_ids=["46026"])
    empty_a = _spot(id="berkeley_marina", buoy_ids=[])
    empty_b = _spot(id="angel_island_ayala", buoy_ids=[])
    later = START + timedelta(hours=30)
    assert adapter.cache_key(buoy, START, END) != adapter.cache_key(empty_a, START, END)
    assert "46026" not in adapter.cache_key(empty_a, START, END)
    assert adapter.cache_key(empty_a, START, END) != adapter.cache_key(empty_b, START, END)
    assert adapter.cache_key(buoy, START, END) != adapter.cache_key(buoy, later, later + timedelta(hours=6))
    same_hour = START.replace(microsecond=123)
    assert adapter.cache_key(buoy, START, END) == adapter.cache_key(buoy, same_hour, END)

    cached = await adapter.fetch(buoy, START, END)
    assert cached.data.station_id == "46026"
    missed = await NdbcAdapter(cache).fetch(empty_a, START, END)
    assert missed.status == SourceStatus.down
    assert missed.data is None
    assert missed.cache_hit is False
    assert "cannot_confirm" in " ".join(missed.notes)
    assert await cache.get(adapter.cache_key(empty_a, START, END)) is None


def test_registry_keeps_distinct_tide_products_and_nws():
    registry = AdapterRegistry(MemoryTTLCache())
    names = set(registry.names())
    assert {"coops_tides", "coops_tides_interval", "coops_currents", "ndbc_buoy", "nws_alerts"} <= names
    assert registry.get("coops_tides").interval == "hilo"
    assert registry.get("coops_tides_interval").interval == "6"
    assert registry.get("coops_tides").name == "coops_tides"
    assert registry.get("nws_alerts").safety_critical is True
