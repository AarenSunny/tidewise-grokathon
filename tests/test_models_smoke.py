"""Phase 1: models and config load without error."""

from backend.config import load_activity_config, load_region
from backend.models.common import Activity
from backend.models.intent import QueryIntent


def test_region_loads():
    region = load_region()
    assert region.id == "sf_bay_coast"
    assert len(region.spots) >= 3


def test_clamming_config_loads():
    cfg = load_activity_config("clamming")
    assert cfg["activity"] == "clamming"
    assert "gates" in cfg


def test_intent_incomplete_without_place():
    intent = QueryIntent(activity=Activity.clamming)
    assert intent.is_complete is False
