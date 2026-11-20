"""GET /recommend lat/lon nearby selection."""

import pytest
from fastapi.testclient import TestClient

from backend import api as api_mod


@pytest.fixture(autouse=True)
def _no_live_fanout(monkeypatch):
    monkeypatch.setattr(api_mod.orchestrator, "sources", ())


client = TestClient(api_mod.app)


def test_recommend_nearby_returns_spot_ids():
    r = client.get(
        "/recommend",
        params={"activity": "clamming", "lat": 37.5, "lon": -122.48, "limit": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["activity"] == "clamming"
    assert len(body["spot_ids"]) >= 1
    assert "pillar_point_harbor" in body["spot_ids"]
    assert body["recommendations"]
    assert body["note"]


def test_recommend_bay_spot_no_dungeness_activity_filter():
    r = client.get(
        "/recommend",
        params={"activity": "crabbing", "lat": 37.5, "lon": -122.48},
    )
    assert r.status_code == 200
    assert "crissy_field" not in r.json()["spot_ids"]


def test_health_lists_registered_adapters():
    r = client.get("/health")
    assert r.status_code == 200
    names = {a["source_name"] for a in r.json()["adapters"]}
    assert "coops_tides" in names
    assert "coops_tides_interval" in names
    assert "coops_currents" in names
    assert "ndbc_buoy" in names
    assert "nws_alerts" in names
    assert "erddap_chl" in names
    assert "cdph_shellfish" in names


def test_recommend_orders_by_distance_and_reports_it():
    r = client.get(
        "/recommend",
        params={"activity": "clamming", "lat": 37.502, "lon": -122.487, "limit": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["spot_ids"][0] == "pillar_point_harbor"
    distances = [body["distances_km"][sid] for sid in body["spot_ids"]]
    assert distances == sorted(distances)
    assert body["distances_km"]["pillar_point_harbor"] < 1
    assert body["recommendations"][0]["distance_km"] == body["distances_km"]["pillar_point_harbor"]


def test_recommend_requires_lat_and_lon_together():
    missing_lon = client.get("/recommend", params={"activity": "swimming", "lat": 37.5})
    missing_lat = client.get("/recommend", params={"activity": "swimming", "lon": -122.5})
    assert missing_lon.status_code == 422
    assert missing_lat.status_code == 422


def test_recommend_rejects_out_of_range_and_non_finite_coordinates():
    bad = client.get("/recommend", params={"activity": "swimming", "lat": 91, "lon": -122.5})
    assert bad.status_code == 422
    nan = client.get("/recommend", params={"activity": "swimming", "lat": "nan", "lon": -122.5})
    assert nan.status_code == 422


def test_recommend_outside_bbox_still_returns_distances():
    r = client.get("/recommend", params={"activity": "swimming", "lat": 0, "lon": 0, "limit": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["spot_ids"]
    assert "outside" in body["note"].lower()
    assert body["distances_km"][body["spot_ids"][0]] > 100


def test_recommend_rejects_naive_window_and_reversed_window():
    naive = client.get(
        "/recommend",
        params={"activity": "sailing", "start": "2026-11-19T12:00:00"},
    )
    assert naive.status_code == 422
    reversed_window = client.get(
        "/recommend",
        params={
            "activity": "sailing",
            "start": "2026-11-20T00:00:00Z",
            "end": "2026-11-19T00:00:00Z",
        },
    )
    assert reversed_window.status_code == 422


def test_recommend_named_spot_rejects_unsupported_activity():
    r = client.get(
        "/recommend",
        params={"activity": "clamming", "spot": "crissy_field"},
    )
    assert r.status_code == 400


def test_recommend_unknown_spot_is_404():
    r = client.get("/recommend", params={"activity": "sailing", "spot": "not_a_spot"})
    assert r.status_code == 404


def test_spots_populated_from_region_yaml():
    r = client.get("/spots")
    assert r.status_code == 200
    spots = r.json()["spots"]
    assert len(spots) >= 10
    pillar = next(s for s in spots if s["id"] == "pillar_point_harbor")
    assert pillar["tide_station_id"] == "9414131"
