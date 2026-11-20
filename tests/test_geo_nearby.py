"""Spot selection: distance, no-take, and Dungeness prohibition."""

from backend.geo.nearby import activity_eligible, nearest_spots, select_spots
from backend.models.common import Activity
from backend.models.spots import Spot


def _spot(spot_id, *, activities, lat=37.5, lon=-122.5, no_take=False, dungeness=False):
    return Spot(
        id=spot_id,
        name=spot_id,
        lat=lat,
        lon=lon,
        activities=activities,
        no_take=no_take,
        dungeness_prohibited=dungeness,
    )


def test_nearest_excludes_no_take_clamming_and_bay_dungeness():
    spots = [
        _spot("open_flat", activities=[Activity.clamming, Activity.crabbing], lat=37.50, lon=-122.48),
        _spot("reserve", activities=[Activity.clamming], lat=37.51, lon=-122.48, no_take=True),
        _spot("bay_pier", activities=[Activity.crabbing], lat=37.52, lon=-122.48, dungeness=True),
    ]
    clamming = nearest_spots(spots, lat=37.5, lon=-122.48, activity=Activity.clamming, limit=5)
    assert [s.id for s, _ in clamming] == ["open_flat"]
    crabbing = nearest_spots(spots, lat=37.5, lon=-122.48, activity=Activity.crabbing, limit=5)
    assert [s.id for s, _ in crabbing] == ["open_flat"]
    assert activity_eligible(spots[1], Activity.swimming) is False


def test_select_spots_tie_breaks_by_id_and_rejects_partial_point():
    spots = [
        _spot("b_beach", activities=[Activity.swimming], lat=37.0, lon=-122.0),
        _spot("a_beach", activities=[Activity.swimming], lat=37.0, lon=-122.0),
    ]
    selected, distances, _notes = select_spots(
        spots, Activity.swimming, lat=37.0, lon=-122.0, limit=2
    )
    assert [s.id for s in selected] == ["a_beach", "b_beach"]
    assert distances["a_beach"] == 0
    try:
        select_spots(spots, Activity.swimming, lat=37.0, lon=None)
        raised = False
    except ValueError:
        raised = True
    assert raised
