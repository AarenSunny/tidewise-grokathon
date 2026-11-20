"""GET /score always returns one window, including when live feeds are absent."""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend import api as api_mod
from backend.models.common import Activity
from backend.scorers.window import resolve_spot, score_window

client = TestClient(api_mod.app)


def test_fallback_window_is_never_empty():
    spot = resolve_spot(api_mod.region, Activity.crabbing, location="Half Moon Bay")
    now = datetime(2026, 11, 19, 20, 0, tzinfo=timezone.utc)
    window = score_window(Activity.crabbing, spot, now=now)
    assert window.spot_id == "pillar_point_harbor"
    assert window.location.startswith("Pillar Point")
    assert window.start < window.end
    assert 0 <= window.score <= 100
    assert "unavailable" in window.reason.lower() or "fallback" in window.reason.lower()
    assert window.reason.strip()


def test_low_tide_window_uses_live_prediction():
    spot = resolve_spot(api_mod.region, Activity.clamming, spot_id="pillar_point_harbor")
    now = datetime(2026, 11, 19, 16, 0, tzinfo=timezone.utc)
    low = now + timedelta(hours=5)
    window = score_window(
        Activity.clamming,
        spot,
        now=now,
        tide_points=[(low, -0.4, "L"), (low + timedelta(hours=6), 4.2, "H")],
        live_tide=True,
    )
    assert window.start <= low <= window.end
    assert window.score >= 60
    assert "low tide" in window.reason.lower()
    assert "noaa" in window.reason.lower()


def test_score_endpoint_half_moon_bay_swimming(monkeypatch):
    async def no_live(registry, spot, start, end):
        return {
            "tide_points": [],
            "slack_times": [],
            "sunrise": None,
            "sunset": None,
            "live_tide": False,
            "live_slack": False,
            "live_daylight": False,
        }

    monkeypatch.setattr(api_mod, "collect_signals", no_live)
    response = client.get(
        "/score",
        params={"activity": "swimming", "location": "Half Moon Bay"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["activity"] == "swimming"
    assert body["spot_id"] == "half_moon_bay_state_beach"
    assert body["location"]
    assert body["start"] < body["end"]
    assert body["reason"]
    assert 0 <= body["score"] <= 100


def test_score_endpoint_unknown_location():
    response = client.get("/score", params={"activity": "swimming", "location": "nowhere creek"})
    assert response.status_code == 404
