"""Bloom flag from VIIRS chlorophyll-a and the region thresholds in region.yaml.

Outer coast: chl-a above 5 mg m^-3 is a bloom (Nezlin et al. 2012).
SF Bay: 13 mg m^-3 is the protective level; 25–40 mg m^-3 is at risk
(Sutula et al. 2017). Missing or stale satellite data cannot confirm a clear.
"""

from __future__ import annotations

from typing import Any

from backend.config.safety import load_region_rules
from backend.features.timeutil import to_la
from backend.models.common import SourceStatus
from backend.models.features import BloomFlag, ChlorophyllObservation, SpotFeatureGrid

_CLEAR_STATUSES = {SourceStatus.ok}


def bloom_status(
    grid: SpotFeatureGrid,
    activity_config: dict[str, Any],
    region_rules: dict[str, Any] | None = None,
) -> BloomFlag:
    """Judge one spot. ``bloom`` is None when the reading cannot be confirmed."""

    rules = region_rules if region_rules is not None else load_region_rules()
    region_id = resolve_region(grid, rules)
    observation = grid.chlorophyll
    if observation is None:
        return BloomFlag(
            spot_id=grid.spot_id,
            region_id=region_id,
            bloom=None,
            cannot_confirm=True,
            reason="chlorophyll observation is missing",
        )
    observed_at = to_la(observation.observed_at, "chlorophyll observed_at")
    if observation.source_status not in _CLEAR_STATUSES:
        return BloomFlag(
            spot_id=grid.spot_id,
            region_id=region_id,
            bloom=None,
            cannot_confirm=True,
            chl_mg_m3=observation.chl_mg_m3,
            observed_at=observed_at,
            reason=f"satellite_chl is {observation.source_status.value}",
        )
    if observation.chl_mg_m3 is None or _chlorophyll_unusable(observation.chl_mg_m3):
        return BloomFlag(
            spot_id=grid.spot_id,
            region_id=region_id,
            bloom=None,
            cannot_confirm=True,
            chl_mg_m3=observation.chl_mg_m3,
            observed_at=observed_at,
            reason="chlorophyll value is missing or a sentinel",
        )
    if region_id is None:
        return BloomFlag(
            spot_id=grid.spot_id,
            region_id=None,
            bloom=None,
            cannot_confirm=True,
            chl_mg_m3=observation.chl_mg_m3,
            observed_at=observed_at,
            reason="bloom region is unknown",
        )
    threshold, at_risk, reason, failed = _compare(observation, region_id, activity_config, rules)
    if threshold is None:
        return BloomFlag(
            spot_id=grid.spot_id,
            region_id=region_id,
            bloom=None,
            cannot_confirm=True,
            chl_mg_m3=observation.chl_mg_m3,
            observed_at=observed_at,
            reason=reason,
        )
    return BloomFlag(
        spot_id=grid.spot_id,
        region_id=region_id,
        bloom=failed,
        cannot_confirm=False,
        chl_mg_m3=observation.chl_mg_m3,
        observed_at=observed_at,
        threshold_mg_m3=threshold,
        at_risk=at_risk,
        reason=reason,
    )


def resolve_region(grid: SpotFeatureGrid, region_rules: dict[str, Any]) -> str | None:
    if grid.bloom_region:
        return grid.bloom_region
    mapped = region_rules.get("spot_regions", {}).get(grid.spot_id)
    return mapped if isinstance(mapped, str) else None


def _compare(
    observation: ChlorophyllObservation,
    region_id: str,
    activity_config: dict[str, Any],
    rules: dict[str, Any],
) -> tuple[float | None, bool | None, str, bool]:
    regions = rules.get("bloom_regions", {})
    spec = regions.get(region_id)
    bloom_cfg = activity_config.get("bloom", {})
    fail_above = bloom_cfg.get("fail_above", {})
    if not isinstance(spec, dict) or region_id not in fail_above:
        return None, None, f"no bloom threshold configured for region {region_id}", True
    key = fail_above[region_id]
    if key not in spec:
        return None, None, f"bloom threshold {key} is missing for {region_id}", True
    threshold = float(spec[key])
    chl = float(observation.chl_mg_m3)  # type: ignore[arg-type]
    at_risk = _in_at_risk_band(chl, region_id, spec, bloom_cfg)
    failed = chl > threshold
    if failed and at_risk:
        reason = (
            f"chlorophyll {chl} mg m^-3 is above {threshold} mg m^-3"
            " and inside the at-risk band"
        )
    elif failed:
        reason = f"chlorophyll {chl} mg m^-3 is above {threshold} mg m^-3"
    else:
        reason = f"chlorophyll {chl} mg m^-3 is at or below {threshold} mg m^-3"
    return threshold, at_risk, reason, failed


def _in_at_risk_band(
    chl: float,
    region_id: str,
    spec: dict[str, Any],
    bloom_cfg: dict[str, Any],
) -> bool:
    band = bloom_cfg.get("at_risk_band", {}).get(region_id)
    if not isinstance(band, list) or len(band) != 2:
        return False
    low_key, high_key = band
    if low_key not in spec or high_key not in spec:
        return False
    return chl >= float(spec[low_key])


def _chlorophyll_unusable(value: float) -> bool:
    if value != value or value in (float("inf"), float("-inf")):
        return True
    if value < 0 or value > 500 or value <= -999:
        return True
    return False
