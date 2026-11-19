"""Season / gear status from DATA_SOURCES.md @ ed08814."""

from datetime import date

from backend.models.spots import Spot
from backend.models.common import Activity
from backend.seasons import (
    crabbing_season_status,
    gear_status,
    zone_for_lat,
)


def _ocean_spot(**kwargs):
    defaults = dict(
        id="pillar_point_harbor",
        name="Pillar Point",
        lat=37.502,
        lon=-122.487,
        activities=[Activity.crabbing],
    )
    defaults.update(kwargs)
    return Spot(**defaults)


def _bay_spot():
    return Spot(
        id="crissy_field",
        name="Crissy Field",
        lat=37.804,
        lon=-122.466,
        activities=[Activity.sailing],
        dungeness_prohibited=True,
    )


def test_zone_3_for_hmb_lat():
    z = zone_for_lat(37.502)
    assert z is not None
    assert z["id"] == "zone_3"


def test_trap_closed_until_2027_01_01():
    gs = gear_status("trap", as_of=date(2026, 11, 19), lat=37.502)
    assert gs.outcome == "closed"
    assert gs.gate_fail is True


def test_trap_allowed_after_restriction():
    gs = gear_status("trap", as_of=date(2027, 1, 1), lat=37.502)
    assert gs.outcome == "allowed"


def test_hoop_net_allowed_during_restriction():
    gs = gear_status("hoop_net", as_of=date(2026, 11, 19), lat=37.502)
    assert gs.outcome == "allowed"
    assert gs.cannot_confirm is False


def test_snare_and_loop_trap_allowed_with_caveat():
    for g in ("snare", "loop_trap"):
        gs = gear_status(g, as_of=date(2026, 11, 19), lat=37.502)
        assert gs.outcome == "allowed"
        assert gs.caveat  # visible caveat — never silent pass


def test_hand_allowed():
    gs = gear_status("hand", as_of=date(2026, 11, 19), lat=37.502)
    assert gs.outcome == "allowed"


def test_unknown_gear_cannot_confirm():
    gs = gear_status("scuba_spear", as_of=date(2026, 11, 19), lat=37.502)
    assert gs.outcome == "cannot_confirm"
    assert gs.cannot_confirm is True


def test_sf_bay_dungeness_hard_fail_not_cannot_confirm():
    st = crabbing_season_status(_bay_spot(), as_of=date(2026, 11, 19))
    assert st.season_open is False
    assert st.dungeness_prohibited_area is True
    for g, gs in st.gear.items():
        assert gs.gate_fail is True
        assert gs.outcome == "closed"
        assert gs.cannot_confirm is False


def test_ocean_spot_season_open_nov19():
    st = crabbing_season_status(_ocean_spot(), as_of=date(2026, 11, 19))
    assert st.season_open is True
    assert st.zone_id == "zone_3"
    assert "ed08814" in st.source
