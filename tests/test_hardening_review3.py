"""review3 P3-2 (freshness), review1 #1 (eligible), review1 #6 (bounded sync calls)."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import BaseModel, ValidationError

from backend.adapters.base import SourceAdapter
from backend.adapters.registry import AdapterRegistry
from backend.cache.memory import MemoryTTLCache
from backend.models.common import Confidence, GateResult, SourceStatus
from backend.models.scoring import ScoredWindow
from backend.models.sources import SourceResult
from backend.models.spots import Spot

UTC = timezone.utc
SPOT = Spot(id="test_spot", name="t", lat=37.5, lon=-122.4)


class _Payload(BaseModel):
    v: float = 1.0
    observed_at: datetime | None = None


class _Adapter(SourceAdapter):
    name = "unit_fresh"
    max_age = timedelta(hours=1)
    max_stale_age = timedelta(hours=6)
    max_retries = 1
    payload_model = _Payload
    observed: datetime | None = None
    validate_sleep_s = 0.0

    async def _fetch_live(self, spot, start, end):
        return {"v": 1.0}

    def _validate(self, raw):
        if self.validate_sleep_s:
            time.sleep(self.validate_sleep_s)
        return _Payload(v=raw["v"], observed_at=self.observed)


def _fetch(adapter):
    now = datetime.now(UTC)
    return asyncio.run(adapter.fetch(SPOT, now, now + timedelta(hours=1)))


def _adapter(observed, **attrs):
    a = _Adapter(MemoryTTLCache())
    a.observed = observed
    for k, v in attrs.items():
        setattr(a, k, v)
    return a


# --- P3-2 ------------------------------------------------------------------
def test_observed_at_none_is_not_fresh():
    r = _fetch(_adapter(None))
    assert r.status != SourceStatus.ok
    assert "observed_at_missing_not_fresh" in r.notes


def test_observed_at_none_safety_critical_is_down():
    r = _fetch(_adapter(None, safety_critical=True))
    assert r.status == SourceStatus.down


def test_future_observed_at_is_invalid_not_fresh():
    r = _fetch(_adapter(datetime.now(UTC) + timedelta(hours=2)))
    assert r.status == SourceStatus.down
    assert any("observed_at_in_future_invalid" in n for n in r.notes)


def test_small_future_skew_tolerated():
    r = _fetch(_adapter(datetime.now(UTC) + timedelta(minutes=2)))
    assert r.status == SourceStatus.ok


def test_future_skew_configurable(monkeypatch):
    monkeypatch.setenv("ADAPTER_MAX_FUTURE_SKEW_S", "7200")
    r = _fetch(_adapter(datetime.now(UTC) + timedelta(hours=1)))
    assert r.status == SourceStatus.ok
    r2 = _fetch(_adapter(datetime.now(UTC) + timedelta(hours=1), max_future_skew=timedelta(0)))
    assert r2.status == SourceStatus.down


def test_forward_looking_feed_may_opt_in():
    a = _adapter(datetime.now(UTC) + timedelta(hours=40), allows_future_observed_at=True)
    assert _fetch(a).status == SourceStatus.ok


def test_registry_marks_only_prediction_feeds_forward_looking():
    reg = AdapterRegistry()
    fwd = {n for n, a in reg.all().items() if a.allows_future_observed_at}
    assert {"coops_tides", "coops_currents"} <= fwd
    for strict in ("ndbc_buoy", "erddap_chl", "erddap_sst", "cdph_shellfish", "beachwatch_bacteria"):
        assert reg.get(strict).allows_future_observed_at is False


def test_cached_result_with_missing_observed_at_is_not_fresh():
    a = _adapter(datetime.now(UTC))
    a.observed = datetime.now(UTC)
    first = _fetch(a)
    assert first.status == SourceStatus.ok
    # same adapter/cache: poison the cached entry's observed_at to None
    key = a.cache_key(SPOT, datetime.now(UTC), datetime.now(UTC) + timedelta(hours=1))
    entry = asyncio.run(a.cache.get(key))
    entry["observed_at"] = None
    entry["data"]["observed_at"] = None
    asyncio.run(a.cache.set(key, entry, timedelta(hours=1)))
    second = _fetch(a)
    assert second.cache_hit and second.status != SourceStatus.ok


# --- review1 #6 ------------------------------------------------------------
def test_hanging_sync_validator_times_out_to_down():
    a = _adapter(datetime.now(UTC), validate_timeout_s=0.1, validate_sleep_s=1.5)

    async def run():
        now = datetime.now(UTC)
        t0 = time.monotonic()
        res = await a.fetch(SPOT, now, now + timedelta(hours=1))
        return res, time.monotonic() - t0

    r, elapsed = asyncio.run(run())  # (asyncio.run itself joins the worker thread afterwards)
    assert elapsed < 1.0  # fetch returned without waiting for the hung parse
    assert r.status == SourceStatus.down
    assert r.data is None
    assert any("validator timed out" in n for n in r.notes)


# --- review1 #1 ------------------------------------------------------------
def _window(**kw):
    now = datetime.now(UTC)
    base = dict(
        spot_id="test_spot",
        start=now,
        end=now + timedelta(hours=1),
        score=50.0,
        confidence=Confidence(value=0.5),
    )
    base.update(kw)
    return ScoredWindow(**base)


def _gate(**kw):
    return GateResult(name="g", reason="r", **kw)


def test_eligible_true_without_gates_rejected():
    with pytest.raises(ValidationError, match="eligible=True requires"):
        _window(eligible=True)


def test_eligible_true_with_failing_gate_rejected():
    with pytest.raises(ValidationError, match="eligible=True requires"):
        _window(eligible=True, gates=[_gate(passed=True), _gate(passed=False)])


def test_eligible_true_with_cannot_confirm_gate_rejected():
    with pytest.raises(ValidationError, match="eligible=True requires"):
        _window(eligible=True, gates=[_gate(passed=False, cannot_confirm=True)])


def test_eligible_true_with_all_gates_passed_ok():
    w = _window(eligible=True, gates=[_gate(passed=True), _gate(passed=True)])
    assert w.eligible and w.gates_all_passed


def test_default_window_not_eligible():
    assert _window().eligible is False
    assert _window(gates=[_gate(passed=False, cannot_confirm=True)]).eligible is False


def test_source_result_import_sanity():
    assert SourceResult  # keeps import used for linting
