"""P3-1: CDPH ArcGIS error/empty must not read as 'no advisory'."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.adapters.cdph import CdphShellfishAdapter
from backend.cache.memory import MemoryTTLCache
from backend.models.common import Activity, SourceStatus
from backend.models.spots import Spot

AS_OF = datetime(2026, 11, 19, 20, tzinfo=timezone.utc)
# 2020-08-25T00:00:00Z — the county-pin layer edit time from REVIEW_2 / P3-1.
LAYER_EDIT_MS = 1598313600000


def _spot() -> Spot:
    return Spot(
        id="pillar_point_harbor",
        name="Pillar Point",
        lat=37.502,
        lon=-122.487,
        activities=[Activity.clamming],
        county="San Mateo County",
    )


def _adapter() -> CdphShellfishAdapter:
    return CdphShellfishAdapter(MemoryTTLCache())


async def _fetch(raw: dict):
    adapter = _adapter()

    async def fake_live(spot, start, end):
        return raw

    adapter._fetch_live = fake_live  # type: ignore[method-assign]
    return await adapter.fetch(_spot(), AS_OF, AS_OF + timedelta(days=1))


def test_validate_error_body_is_not_a_clear():
    payload = _adapter()._validate(
        {
            "special": {"error": {"code": 400, "message": "Unable to complete operation."}},
            "counties": {"error": {"code": 500, "message": "Service unavailable"}},
        }
    )
    assert payload.cannot_confirm is True
    assert payload.any_region_advisory is None
    assert payload.observed_at is None


def test_validate_empty_features_is_not_a_clear():
    payload = _adapter()._validate(
        {"special": {"features": []}, "counties": {"features": []}}
    )
    assert payload.cannot_confirm is True
    assert payload.any_region_advisory is None
    assert payload.observed_at is None


def test_validate_uses_layer_edit_time_not_the_clock():
    before = datetime.now(timezone.utc)
    payload = _adapter()._validate(
        {
            "special": {
                "error": {"code": 400, "message": "failed"},
                "editingInfo": {"lastEditDate": LAYER_EDIT_MS},
            },
            "counties": {"features": []},
        }
    )
    after = datetime.now(timezone.utc)
    assert payload.observed_at == datetime.fromtimestamp(LAYER_EDIT_MS / 1000, tz=timezone.utc)
    assert payload.observed_at is not None
    assert not (before <= payload.observed_at <= after)
    assert payload.cannot_confirm is True
    assert payload.any_region_advisory is None


def test_county_pins_are_not_a_clear_or_a_closure():
    payload = _adapter()._validate(
        {
            "special": {"features": []},
            "counties": {
                "features": [
                    {"attributes": {"County_Name": "San Mateo County"}},
                    {"attributes": {"County_Name": "Marin County"}},
                ]
            },
        }
    )
    assert payload.cannot_confirm is True
    assert payload.any_region_advisory is None
    assert payload.observed_at is None
    assert "San Mateo County" in payload.region_counties_with_symbol


@pytest.mark.asyncio
async def test_fetch_error_body_is_down_cannot_confirm():
    result = await _fetch(
        {
            "special": {"error": {"code": 400, "message": "Unable to complete operation."}},
            "counties": {"features": []},
        }
    )
    assert result.status == SourceStatus.down
    assert result.data is not None
    assert result.data.cannot_confirm is True
    assert result.data.any_region_advisory is None
    assert result.observed_at is None
    assert any("cannot_confirm" in note for note in result.notes)


@pytest.mark.asyncio
async def test_fetch_empty_layers_are_down_not_ok():
    result = await _fetch({"special": {"features": []}, "counties": {"features": []}})
    assert result.status == SourceStatus.down
    assert result.data.cannot_confirm is True
    assert result.data.any_region_advisory is not False
    assert result.observed_at is None
