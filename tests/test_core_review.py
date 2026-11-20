"""Core-track tests for review1 #7/#13/#14/#15/#16 and orchestrator."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.adapters.base import PermanentFetchError, SourceAdapter, TransientFetchError
from backend.cache.memory import MemoryTTLCache
from backend.models.common import Activity, SourceStatus
from backend.models.spots import Spot
from backend.redact import redact
from backend.settings import Settings


def _spot() -> Spot:
    return Spot(
        id="pillar_point_harbor",
        name="Pillar Point",
        lat=37.502,
        lon=-122.487,
        activities=[Activity.clamming],
    )


@pytest.mark.asyncio
async def test_permanent_error_not_retried():
    calls = {"n": 0}

    class Fake(SourceAdapter):
        name = "fake_perm"
        max_retries = 3

        async def _fetch_live(self, spot, start, end):
            calls["n"] += 1
            raise PermanentFetchError("bad request 400")

        def _validate(self, raw):
            return raw

    adapter = Fake(MemoryTTLCache())
    start = datetime(2026, 11, 19, tzinfo=timezone.utc)
    result = await adapter.fetch(_spot(), start, start + timedelta(hours=1))
    assert result.status == SourceStatus.down
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_retry_after_honoured():
    sleeps: list[float] = []
    calls = {"n": 0}

    class Fake(SourceAdapter):
        name = "fake_429"
        max_retries = 2
        backoff_base_s = 10.0

        async def _fetch_live(self, spot, start, end):
            calls["n"] += 1
            if calls["n"] == 1:
                raise TransientFetchError("rate limited", retry_after_s=0.01)
            return {"ok": True}

        def _validate(self, raw):
            return {"ok": True, "observed_at": datetime.now(timezone.utc)}

    adapter = Fake(MemoryTTLCache())
    start = datetime(2026, 11, 19, tzinfo=timezone.utc)

    real_sleep = asyncio.sleep

    async def spy_sleep(delay):
        sleeps.append(delay)
        await real_sleep(0)

    asyncio.sleep = spy_sleep  # type: ignore[assignment]
    try:
        result = await adapter.fetch(_spot(), start, start + timedelta(hours=1))
    finally:
        asyncio.sleep = real_sleep  # type: ignore[assignment]
    assert result.status in {SourceStatus.ok, SourceStatus.stale}
    assert calls["n"] == 2
    assert sleeps and sleeps[0] == pytest.approx(0.01, abs=0.001)


@pytest.mark.asyncio
async def test_single_flight_one_live_call():
    calls = {"n": 0}
    started = asyncio.Event()
    release = asyncio.Event()

    class Fake(SourceAdapter):
        name = "fake_sf"
        max_retries = 1

        async def _fetch_live(self, spot, start, end):
            calls["n"] += 1
            started.set()
            await release.wait()
            return {"v": 1}

        def _validate(self, raw):
            return {"v": 1, "observed_at": datetime.now(timezone.utc)}

    adapter = Fake(MemoryTTLCache())
    start = datetime(2026, 11, 19, tzinfo=timezone.utc)
    end = start + timedelta(hours=1)
    t1 = asyncio.create_task(adapter.fetch(_spot(), start, end))
    await started.wait()
    t2 = asyncio.create_task(adapter.fetch(_spot(), start, end))
    await asyncio.sleep(0.05)
    release.set()
    r1, r2 = await asyncio.gather(t1, t2)
    assert calls["n"] == 1
    assert r1.status == r2.status == SourceStatus.ok


def test_redact_strips_key_query_and_paths():
    s = redact(
        "fail https://api.example/v1?api_key=SECRET123&x=1 /workspace/tidewise-core/foo"
    )
    assert "SECRET123" not in s
    assert "tidewise-core" not in s
    assert "[REDACTED]" in s or "[PATH]" in s


def test_spot_id_validation():
    with pytest.raises(ValueError):  # pydantic.ValidationError subclasses ValueError
        Spot(id="Bad-ID", name="x", lat=1, lon=2, activities=[])


def test_settings_cors_parses():
    s = Settings(cors_origins="http://localhost:5173,http://127.0.0.1:5173", debug=False)
    assert "http://localhost:5173" in s.cors_origin_list()
    assert s.debug is False


def test_debug_endpoints_gated(monkeypatch):
    from backend import api as api_mod

    monkeypatch.setattr(api_mod.settings, "debug", False)
    client = TestClient(api_mod.app)
    r = client.post("/debug/fail/coops_tides")
    assert r.status_code == 404


def test_recommend_via_orchestrator_no_live(monkeypatch):
    from backend import api as api_mod

    # Avoid live upstream fan-out in unit tests
    monkeypatch.setattr(api_mod.orchestrator, "sources", ())
    client = TestClient(api_mod.app)
    r = client.get(
        "/recommend",
        params={"activity": "clamming", "lat": 37.5, "lon": -122.48, "limit": 3},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["spot_ids"]
    assert body["note"]


def test_query_no_longer_501():
    from backend.api import app

    client = TestClient(app)
    r = client.post("/query", json={"text": "where to clam near HMB?"})
    assert r.status_code == 200
    assert r.json()["explanation"]


def test_query_text_max_length():
    from backend.api import app

    client = TestClient(app)
    r = client.post("/query", json={"text": "x" * 2001})
    assert r.status_code == 422
