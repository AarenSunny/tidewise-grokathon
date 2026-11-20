"""review2 N3: SF/San Pablo Bay + Dungeness is blocked end to end (fail, not cannot_confirm)."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend import api as api_mod
from backend.config import load_region
from backend.models.common import Activity


@pytest.fixture(autouse=True)
def _no_live_fanout(monkeypatch):
    monkeypatch.setattr(api_mod.orchestrator, "sources", ())


client = TestClient(api_mod.app)
REGION = load_region()
BAY_SPOTS = [s for s in REGION.spots if s.dungeness_prohibited]


def test_region_flags_bay_spots_dungeness_prohibited():
    ids = {s.id for s in BAY_SPOTS}
    assert {"crissy_field", "aquatic_park", "angel_island_ayala", "berkeley_marina"} <= ids


def test_no_prohibited_spot_offers_crabbing():
    for s in BAY_SPOTS:
        assert Activity.crabbing not in s.activities, s.id


@pytest.mark.parametrize("spot_id", [s.id for s in BAY_SPOTS])
def test_api_blocks_crabbing_at_bay_spot(spot_id):
    r = client.get("/recommend", params={"activity": "crabbing", "spot": spot_id})
    assert r.status_code == 400
    assert "crabbing" in r.json()["detail"]


def test_nearby_crabbing_never_returns_bay_spots_even_from_inside_the_bay():
    # Standing in the middle of SF Bay (37.82, -122.40): bay spots are the nearest,
    # but must still be excluded for crabbing.
    r = client.get(
        "/recommend",
        params={"activity": "crabbing", "lat": 37.82, "lon": -122.40, "limit": 15},
    )
    assert r.status_code == 200
    returned = set(r.json()["spot_ids"])
    assert returned  # ocean crabbing spots still offered
    assert not returned & {s.id for s in BAY_SPOTS}


def test_season_gate_is_hard_fail_for_bay_spot_all_gear():
    """Seasons module (agent B) is read-only here: assert the contract end to end."""
    from backend.seasons import crabbing_season_status

    for s in BAY_SPOTS:
        st = crabbing_season_status(s, as_of=date(2026, 11, 19))
        assert st.dungeness_prohibited_area is True
        assert st.season_open is False
        assert st.gear, "gear table must be present"
        for g in st.gear.values():
            assert g.gate_fail is True  # FAIL, not cannot_confirm
            assert g.cannot_confirm is False
