"""Orchestrator uses activity scorers on fetched payloads. No live network."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.adapters.registry import AdapterRegistry
from backend.config import load_region
from backend.models.common import Activity, SourceStatus
from backend.models.sources import SourceResult
from backend.orchestrator import Orchestrator, SpotFetchBundle

UTC = timezone.utc
START = datetime(2026, 11, 21, 14, tzinfo=UTC)  # 06:00 America/Los_Angeles
END = START + timedelta(hours=8)


def _result(name: str, data, status=SourceStatus.ok) -> SourceResult:
    return SourceResult(
        data=data,
        fetched_at=START,
        valid_until=END,
        status=status,
        source_name=name,
        observed_at=START,
    )


def _bundle_results(*, chl_status=SourceStatus.ok, county_hit=False):
    tides = SimpleNamespace(
        points=[
            SimpleNamespace(t=datetime(2026, 11, 21, 13, tzinfo=UTC), v_ft_mllw=1.2, type="H"),
            SimpleNamespace(t=datetime(2026, 11, 21, 15, 30, tzinfo=UTC), v_ft_mllw=-1.6, type="L"),
            SimpleNamespace(t=datetime(2026, 11, 21, 18, tzinfo=UTC), v_ft_mllw=1.0, type="H"),
        ]
    )
    chl = SimpleNamespace(chla_mg_m3=1.5, observed_at=datetime(2026, 11, 20, 9, tzinfo=UTC), stale=False)
    counties = ["San Mateo County"] if county_hit else []
    shellfish = SimpleNamespace(
        special_advisories=[],
        region_counties_with_symbol=counties,
        any_region_advisory=county_hit,
    )
    return {
        "coops_tides": _result("coops_tides", tides),
        "erddap_chl": _result("erddap_chl", chl, chl_status),
        "cdph_shellfish": _result("cdph_shellfish", shellfish),
    }


def _orchestrator() -> Orchestrator:
    return Orchestrator(AdapterRegistry(), region=load_region(), sources=())


@pytest.mark.asyncio
async def test_recommend_without_payloads_runs_scorer_and_stays_ineligible():
    orch = _orchestrator()
    response = await orch.recommend(
        Activity.clamming,
        spot_id="pillar_point_harbor",
        start=START,
        end=END,
    )
    assert response.recommendations
    assert response.recommendations[0].windows == []
    assert response.recommendations[0].best_score is None
    assert "Activity scorers ranked 0" in (response.note or "")


@pytest.mark.asyncio
async def test_recommend_scores_minus_tide_from_tide_payload(monkeypatch):
    orch = _orchestrator()
    results = _bundle_results()

    async def fake_fetch(spot, start, end, sources=None):
        return SpotFetchBundle(spot=spot, results=results)

    monkeypatch.setattr(orch, "fetch_spot_sources", fake_fetch)
    response = await orch.recommend(
        Activity.clamming,
        spot_id="pillar_point_harbor",
        start=START,
        end=END,
    )
    rec = response.recommendations[0]
    assert rec.windows
    assert rec.windows[0].factors
    assert rec.windows[0].label
    assert any(window.eligible for window in rec.windows)
    assert rec.best_score is not None
    assert rec.best_score == max(window.score for window in rec.windows if window.eligible)
    assert "eligible" in (response.note or "")


@pytest.mark.asyncio
async def test_shellfish_advisory_blocks_clamming_window(monkeypatch):
    orch = _orchestrator()
    results = _bundle_results(county_hit=True)

    async def fake_fetch(spot, start, end, sources=None):
        return SpotFetchBundle(spot=spot, results=results)

    monkeypatch.setattr(orch, "fetch_spot_sources", fake_fetch)
    response = await orch.recommend(
        Activity.clamming,
        spot_id="pillar_point_harbor",
        start=START,
        end=END,
    )
    windows = response.recommendations[0].windows
    assert windows
    assert all(not window.eligible for window in windows)
    assert response.recommendations[0].best_score is None


@pytest.mark.asyncio
async def test_stale_chlorophyll_cannot_pass(monkeypatch):
    orch = _orchestrator()
    results = _bundle_results(chl_status=SourceStatus.stale)

    async def fake_fetch(spot, start, end, sources=None):
        return SpotFetchBundle(spot=spot, results=results)

    monkeypatch.setattr(orch, "fetch_spot_sources", fake_fetch)
    response = await orch.recommend(
        Activity.clamming,
        spot_id="pillar_point_harbor",
        start=START,
        end=END,
    )
    windows = response.recommendations[0].windows
    assert windows
    assert all(not window.eligible for window in windows)
