"""Optional live smoke for CO-OPS, NDBC, and NWS.

Skipped unless TIDEWISE_LIVE=1. Unit tests must not reach the network.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

from backend.adapters.coops import CoopsCurrentAdapter, CoopsTideAdapter
from backend.adapters.ndbc import NdbcAdapter
from backend.adapters.nws import NwsAlertsAdapter
from backend.cache.memory import MemoryTTLCache
from backend.models.common import Activity, SourceStatus
from backend.models.spots import Spot

pytestmark = pytest.mark.skipif(
    os.getenv("TIDEWISE_LIVE") != "1",
    reason="set TIDEWISE_LIVE=1 to run the live NOAA/NWS smoke test",
)


def _spot() -> Spot:
    return Spot(
        id="pillar_point_harbor",
        name="Pillar Point",
        lat=37.502,
        lon=-122.487,
        activities=[Activity.clamming, Activity.crabbing],
        tide_station_id="9414131",
        current_station_id="SFB1201",
        buoy_ids=["46026"],
        nws_zone="PZZ545",
    )


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_coops_ndbc_nws_smoke():
    spot = _spot()
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    cache = MemoryTTLCache()

    tides = await CoopsTideAdapter(cache).fetch(spot, start, end)
    assert tides.status == SourceStatus.ok
    assert tides.observed_at is not None and tides.observed_at.tzinfo is not None
    assert tides.data.datum == "MLLW"
    assert tides.data.points
    assert all(-6 <= point.v_ft_mllw <= 12 for point in tides.data.points)

    interval = CoopsTideAdapter(cache, interval="6")
    interval.name = "coops_tides_interval"
    six = await interval.fetch(spot, start, end)
    assert six.status == SourceStatus.ok
    assert len(six.data.points) > len(tides.data.points)

    currents = await CoopsCurrentAdapter(cache).fetch(spot, start, end)
    assert currents.status == SourceStatus.ok
    assert currents.data.units == "knots"
    assert currents.observed_at.tzinfo is not None
    assert all(abs(point.velocity_kt) <= 10 for point in currents.data.points)

    buoy = await NdbcAdapter(cache).fetch(spot, start, end)
    assert buoy.status in {SourceStatus.ok, SourceStatus.down}
    if buoy.status == SourceStatus.ok:
        assert buoy.observed_at.tzinfo is not None
        if buoy.data.wspd_kt is not None:
            assert 0 <= buoy.data.wspd_kt <= 150
        if buoy.data.wtmp_c is not None:
            assert -2 <= buoy.data.wtmp_c <= 40

    alerts = await NwsAlertsAdapter(cache).fetch(spot, start, end)
    assert alerts.status == SourceStatus.ok
    assert alerts.observed_at.tzinfo is not None
    assert alerts.data.marine_zone_checked is True
    assert alerts.data.small_craft_advisory is not None
    assert alerts.data.beach_hazard is not None
