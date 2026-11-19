"""Unit tests for adapters: fixtures + mocks only (no live calls)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import httpx

from backend.adapters.base import PermanentFetchError, SourceAdapter
from backend.adapters.coops import CoopsTideAdapter, TidePayload
from backend.adapters.erddap import ErddapChlAdapter, ChlPayload
from backend.adapters.ndbc import NdbcAdapter, parse_ndbc_value
from backend.cache.memory import MemoryTTLCache
from backend.health import HealthMonitor
from backend.models.common import SourceStatus
from backend.models.spots import Spot
from backend.models.common import Activity

FIXTURES = Path(__file__).parent / "fixtures"


def _spot(**kw):
    base = dict(
        id="pillar_point_harbor",
        name="Pillar Point",
        lat=37.502,
        lon=-122.487,
        activities=[Activity.clamming],
        tide_station_id="9414131",
        buoy_ids=["46026"],
    )
    base.update(kw)
    return Spot(**base)


@pytest.mark.asyncio
async def test_coops_error_json_is_permanent():
    cache = MemoryTTLCache()
    adapter = CoopsTideAdapter(cache)
    raw = json.loads((FIXTURES / "coops_error.json").read_text())
    with pytest.raises(PermanentFetchError):
        adapter._validate(raw)


@pytest.mark.asyncio
async def test_coops_ok_fixture_parses():
    cache = MemoryTTLCache()
    adapter = CoopsTideAdapter(cache)
    raw = json.loads((FIXTURES / "coops_tides_ok.json").read_text())
    raw["_station_id"] = "9414290"
    payload = adapter._validate(raw)
    assert isinstance(payload, TidePayload)
    assert len(payload.points) == 3
    assert payload.observed_at is not None
    assert payload.observed_at.tzinfo is not None


@pytest.mark.asyncio
async def test_coops_station_fallback(monkeypatch):
    cache = MemoryTTLCache()
    health = HealthMonitor()
    adapter = CoopsTideAdapter(cache, health=health)
    calls: list[str] = []

    async def fake_get(client, station, start, end):
        calls.append(station)
        if station == "9414131":
            raise PermanentFetchError("no predictions")
        return {
            "predictions": [{"t": "2026-11-19 12:00", "v": "2.0", "type": "L"}],
            "_station_id": station,
            "_fallback_used": f"station:{station}",
        }

    # Permanent on primary should not fall through — PermanentFetchError breaks chain
    # So simulate transient on primary, success on fallback
    async def fake_get2(client, station, start, end):
        calls.append(station)
        if station == "9414131":
            raise ConnectionError("timeout")
        return {
            "predictions": [{"t": "2026-11-19 12:00", "v": "2.0", "type": "L"}],
            "_station_id": station,
            "_fallback_used": f"station:{station}",
        }

    monkeypatch.setattr(adapter, "_get_predictions", fake_get2)
    spot = _spot(tide_station_id="9414131")
    start = datetime(2026, 11, 19, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    raw = await adapter._fetch_live(spot, start, end)
    assert raw["_station_id"] == "9414290"
    assert calls == ["9414131", "9414290"]


def test_ndbc_mm_sentinel():
    assert parse_ndbc_value("MM") is None
    assert parse_ndbc_value("12.0") == 12.0
    assert parse_ndbc_value("999") is None


def test_ndbc_validate_fixture():
    adapter = NdbcAdapter(MemoryTTLCache())
    text = (FIXTURES / "ndbc_sample.txt").read_text()
    obs = adapter._validate({"station_id": "46026", "text": text})
    assert obs.wtmp_c == 18.8
    assert obs.wvht_m == 3.5
    assert obs.dpd_s is None  # MM
    assert obs.observed_at is not None


def test_chl_stale_flag_old_observation():
    adapter = ErddapChlAdapter(MemoryTTLCache())
    raw = json.loads((FIXTURES / "erddap_chl_ok.json").read_text())
    payload = adapter._validate(raw)
    assert isinstance(payload, ChlPayload)
    assert payload.chla_mg_m3 is not None
    # Observation 2026-11-09 vs "today" 2026-11-19 → >10 days → stale
    assert payload.stale is True
    assert payload.observed_at is not None


def test_chl_empty_never_invents_value():
    adapter = ErddapChlAdapter(MemoryTTLCache())
    raw = json.loads((FIXTURES / "erddap_chl_empty.json").read_text())
    payload = adapter._validate(raw)
    assert payload.chla_mg_m3 is None
    assert payload.stale is True


@pytest.mark.asyncio
async def test_cache_key_stable_across_microseconds():
    adapter = CoopsTideAdapter(MemoryTTLCache())
    spot = _spot()
    a = datetime(2026, 11, 19, 15, 0, 0, 123456, tzinfo=timezone.utc)
    b = datetime(2026, 11, 19, 15, 0, 0, 999999, tzinfo=timezone.utc)
    assert adapter.cache_key(spot, a, a + timedelta(hours=1)) == adapter.cache_key(
        spot, b, b + timedelta(hours=1)
    )


@pytest.mark.asyncio
async def test_cache_roundtrip_preserves_payload_type():
    cache = MemoryTTLCache()
    adapter = CoopsTideAdapter(cache)
    spot = _spot(tide_station_id="9414290")
    raw = json.loads((FIXTURES / "coops_tides_ok.json").read_text())
    raw["_station_id"] = "9414290"

    async def fake_live(s, start, end):
        return raw

    adapter._fetch_live = fake_live  # type: ignore[method-assign]
    start = datetime(2026, 11, 19, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    r1 = await adapter.fetch(spot, start, end)
    assert isinstance(r1.data, TidePayload)
    r2 = await adapter.fetch(spot, start, end)
    assert r2.cache_hit is True
    assert isinstance(r2.data, TidePayload)


@pytest.mark.asyncio
async def test_forced_down_via_health_monitor():
    cache = MemoryTTLCache()
    health = HealthMonitor()
    adapter = CoopsTideAdapter(cache, health=health)
    health.register(adapter.name)
    health.set_forced_down(adapter.name, True)
    spot = _spot()
    start = datetime(2026, 11, 19, tzinfo=timezone.utc)
    result = await adapter.fetch(spot, start, start + timedelta(days=1))
    assert result.status == SourceStatus.down
    assert any("forced_down" in n for n in result.notes)


@pytest.mark.asyncio
async def test_observation_age_marks_stale():
    """review1-#2: ancient observed_at ⇒ stale even if HTTP ok."""

    class Fake(SourceAdapter):
        name = "fake_old"
        max_age = timedelta(hours=1)
        max_stale_age = timedelta(days=30)
        payload_model = TidePayload

        async def _fetch_live(self, spot, start, end):
            return {"ok": True}

        def _validate(self, raw):
            return TidePayload(
                station_id="x",
                product="t",
                points=[],
                observed_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
            )

    adapter = Fake(MemoryTTLCache())
    spot = _spot()
    now_start = datetime(2026, 11, 19, tzinfo=timezone.utc)
    result = await adapter.fetch(spot, now_start, now_start + timedelta(hours=1))
    assert result.status == SourceStatus.stale
    assert result.observed_at is not None


@pytest.mark.asyncio
async def test_max_stale_age_returns_down(monkeypatch):
    cache = MemoryTTLCache(default_max_stale_age=timedelta(seconds=1))
    adapter = CoopsTideAdapter(cache)
    adapter.max_stale_age = timedelta(seconds=0)
    spot = _spot()
    start = datetime(2026, 11, 19, tzinfo=timezone.utc)
    # Seed cache with old entry
    from backend.models.sources import SourceResult

    old = SourceResult(
        data={"x": 1},
        fetched_at=datetime(2026, 11, 1, tzinfo=timezone.utc),
        valid_until=datetime(2026, 11, 1, tzinfo=timezone.utc),
        status=SourceStatus.ok,
        source_name=adapter.name,
    )
    key = adapter.cache_key(spot, start, start + timedelta(days=1))
    await cache.set(key, old.model_dump(mode="json"), timedelta(hours=1))
    # Force live fail
    async def boom(*a, **k):
        raise ConnectionError("down")

    adapter._fetch_live = boom  # type: ignore
    # Expire TTL so get() misses but get_stale might hit — max_stale_age=0 ⇒ None
    result = await adapter.fetch(spot, start, start + timedelta(days=1))
    assert result.status == SourceStatus.down
