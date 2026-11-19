"""Config-driven season / gear status (DATA_SOURCES.md @ ed08814).

Zone-based by latitude. SF Bay / San Pablo Bay Dungeness → fail (not cannot_confirm).
Unconfirmed gear → cannot_confirm. Loop traps/snares carry a visible caveat.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal, Optional

import yaml

from backend.models.spots import Spot

CONFIG_PATH = Path(__file__).resolve().parent / "config" / "seasons.yaml"

GearOutcome = Literal["allowed", "closed", "restricted", "cannot_confirm"]


@dataclass
class GearStatus:
    gear: str
    outcome: GearOutcome
    reason: str
    caveat: Optional[str] = None
    cannot_confirm: bool = False
    # For scorers: fail means hard gate fail; cannot_confirm means missing evidence
    gate_fail: bool = False


@dataclass
class SeasonStatus:
    activity: str
    as_of: date
    season_open: bool
    reasons: list[str]
    gear: dict[str, GearStatus]
    zone_id: Optional[str] = None
    dungeness_prohibited_area: bool = False
    source: str = "DATA_SOURCES.md@ed08814"


_CACHE: Optional[dict[str, Any]] = None


def load_seasons(path: Path | None = None) -> dict[str, Any]:
    global _CACHE
    cfg_path = path or CONFIG_PATH
    if _CACHE is not None and path is None:
        return _CACHE
    with cfg_path.open() as f:
        data = yaml.safe_load(f)
    if path is None:
        _CACHE = data
    return data


def _as_date(d: date | datetime | str) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d))


def zone_for_lat(lat: float, cfg: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
    cfg = cfg or load_seasons()
    for z in cfg.get("dungeness", {}).get("zones", []):
        # Inclusive of north/south bounds as quoted
        if z["south_lat"] <= lat <= z["north_lat"]:
            return z
    return None


def is_dungeness_prohibited_spot(spot: Spot, cfg: Optional[dict[str, Any]] = None) -> bool:
    """SF Bay / San Pablo Bay: Dungeness take prohibited — hard fail."""
    if getattr(spot, "dungeness_prohibited", False):
        return True
    cfg = cfg or load_seasons()
    for area in cfg.get("dungeness", {}).get("no_dungeness_areas", []):
        if (
            area["min_lat"] <= spot.lat <= area["max_lat"]
            and area["min_lon"] <= spot.lon <= area["max_lon"]
        ):
            # Only treat bay-side spots (activities include crabbing in bay)
            if spot.id.startswith(("crissy", "aquatic", "berkeley", "richardson", "angel", "sf_bay", "sausalito")):
                return True
            if "bay" in (spot.notes or "").lower() or "bay" in spot.id:
                return True
    # Explicit flag preferred; also check name heuristics for bay waterfront
    return False


def mussel_quarantine_active(as_of: date, cfg: Optional[dict[str, Any]] = None) -> tuple[bool, str]:
    cfg = cfg or load_seasons()
    mq = cfg["mussel_quarantine"]
    lifted = _as_date(mq.get("lifted_end_of_day", "2099-01-01"))
    # Annual window May 1 – Oct 31
    start = date(as_of.year, mq["annual_start_month"], mq["annual_start_day"])
    end = date(as_of.year, mq["annual_end_month"], mq["annual_end_day"])
    in_window = start <= as_of <= end
    if as_of <= lifted and in_window:
        return True, f"annual mussel quarantine {start.isoformat()}–{end.isoformat()}"
    if as_of > lifted:
        return False, f"quarantine lifted end of {lifted.isoformat()} (localized advisories may remain)"
    return False, "outside annual mussel quarantine window"


def gear_status(
    gear: str,
    *,
    as_of: date,
    lat: float,
    cfg: Optional[dict[str, Any]] = None,
) -> GearStatus:
    """Return status for a gear type at lat/date. Unconfirmed gear → cannot_confirm."""
    cfg = cfg or load_seasons()
    gear_key = gear.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {"loop_traps": "loop_trap", "crab_snare": "snare", "snares": "snare", "traps": "trap"}
    gear_key = aliases.get(gear_key, gear_key)

    gear_cfg = (cfg.get("dungeness") or {}).get("gear") or {}
    entry = gear_cfg.get(gear_key)
    if entry is None or not entry.get("confirmed", False):
        return GearStatus(
            gear=gear_key,
            outcome="cannot_confirm",
            reason=f"gear '{gear_key}' not explicitly confirmed in DATA_SOURCES.md@ed08814",
            cannot_confirm=True,
        )

    zone = zone_for_lat(lat, cfg)
    until = entry.get("restricted_until") or (zone or {}).get("trap_restricted_until")
    caveat = entry.get("note") if entry.get("caveat") else None
    if entry.get("caveat"):
        caveat = entry.get("note")

    status = entry.get("status")
    if gear_key == "trap":
        if until and as_of < _as_date(until):
            return GearStatus(
                gear="trap",
                outcome="closed",
                reason=f"traps restricted until at least {until} in Zones 1–5 (Zone 3 covers 38°46.125'N–37°11'N)",
                gate_fail=True,
                caveat=entry.get("note"),
            )
        return GearStatus(
            gear="trap",
            outcome="allowed",
            reason=f"trap restriction ended ({until})",
            caveat=entry.get("note"),
        )

    # hoop_net / snare / loop_trap / hand — confirmed allowed during restriction
    outcome: GearOutcome = "allowed" if status == "allowed" else "cannot_confirm"
    cannot = outcome == "cannot_confirm"
    return GearStatus(
        gear=gear_key,
        outcome=outcome,
        reason=entry.get("note") or f"{gear_key} status={status}",
        caveat=caveat,
        cannot_confirm=cannot,
        gate_fail=False,
    )


def crabbing_season_status(
    spot: Spot,
    as_of: date | datetime | str | None = None,
    *,
    gears: Optional[list[str]] = None,
) -> SeasonStatus:
    cfg = load_seasons()
    day = _as_date(as_of or date.today())
    d = cfg["dungeness"]
    open_d = _as_date(d["season_open_date"])
    close_d = _as_date(d["season_close_date_central"])
    reasons: list[str] = []
    season_open = open_d <= day <= close_d
    if not season_open:
        reasons.append(f"outside recreational Dungeness season {open_d}–{close_d}")
    else:
        reasons.append(f"recreational Dungeness season open ({open_d}–{close_d})")

    prohibited = is_dungeness_prohibited_spot(spot, cfg) or bool(
        getattr(spot, "dungeness_prohibited", False)
    )
    if prohibited:
        season_open = False
        reasons.append(
            "Dungeness take prohibited in San Francisco Bay / San Pablo Bay "
            "(14 CCR §29.85(b)(1)) — gate FAIL"
        )

    zone = zone_for_lat(spot.lat, cfg)
    if zone:
        reasons.append(f"lat {spot.lat:.3f} → {zone['id']} ({zone['name']})")

    # Domoic note only (do not blanket-close)
    da = d.get("domoic_acid_delay") or {}
    if da and da.get("south_lat", 99) <= spot.lat <= da.get("north_lat", -99):
        reasons.append(
            "NOTE: within domoic-acid delay band (Reading Rock–Ten Mile); "
            "verify CDFW before northern trips — not a blanket SF/HMB close"
        )

    gear_list = gears or ["trap", "hoop_net", "snare", "loop_trap", "hand"]
    gear_out: dict[str, GearStatus] = {}
    for g in gear_list:
        gs = gear_status(g, as_of=day, lat=spot.lat, cfg=cfg)
        if prohibited:
            # Area prohibition overrides gear — hard fail for all Dungeness take
            gs = GearStatus(
                gear=gs.gear,
                outcome="closed",
                reason="Dungeness prohibited in SF Bay / San Pablo Bay (§29.85(b)(1))",
                gate_fail=True,
                caveat=gs.caveat,
            )
        gear_out[g] = gs

    return SeasonStatus(
        activity="crabbing",
        as_of=day,
        season_open=season_open and not prohibited,
        reasons=reasons,
        gear=gear_out,
        zone_id=(zone or {}).get("id"),
        dungeness_prohibited_area=prohibited,
        source=f"DATA_SOURCES.md@{cfg.get('source_commit', 'ed08814')}",
    )


def clamming_season_status(
    as_of: date | datetime | str | None = None,
) -> SeasonStatus:
    cfg = load_seasons()
    day = _as_date(as_of or date.today())
    active, reason = mussel_quarantine_active(day, cfg)
    reasons = [reason]
    # Clams generally no universal closed season; mussel quarantine is separate
    return SeasonStatus(
        activity="clamming",
        as_of=day,
        season_open=True,
        reasons=reasons + ["clam species generally open year-round pending CDPH advisories"],
        gear={},
        source=f"DATA_SOURCES.md@{cfg.get('source_commit', 'ed08814')}",
    )
