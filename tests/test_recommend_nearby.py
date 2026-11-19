"""GET /recommend lat/lon nearby selection."""

from fastapi.testclient import TestClient

from backend.api import app


client = TestClient(app)


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
    assert body["recommendations"]  # stubs present
    assert body["note"]


def test_recommend_bay_spot_no_dungeness_activity_filter():
    r = client.get(
        "/recommend",
        params={"activity": "crabbing", "lat": 37.5, "lon": -122.48},
    )
    assert r.status_code == 200
    # Bay-only sailing spots should not appear for crabbing
    assert "crissy_field" not in r.json()["spot_ids"]


def test_health_lists_registered_adapters():
    r = client.get("/health")
    assert r.status_code == 200
    names = {a["source_name"] for a in r.json()["adapters"]}
    assert "coops_tides" in names
    assert "erddap_chl" in names
    assert "cdph_shellfish" in names


def test_spots_populated_from_region_yaml():
    r = client.get("/spots")
    assert r.status_code == 200
    spots = r.json()["spots"]
    assert len(spots) >= 10
    pillar = next(s for s in spots if s["id"] == "pillar_point_harbor")
    assert pillar["tide_station_id"] == "9414131"
