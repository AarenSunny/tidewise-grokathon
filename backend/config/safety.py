"""Region safety tables (bloom cutoffs, crab zones) loaded from region.yaml.

Activity scorers read thresholds from here and from the activity YAML files.
The Spot pydantic model ignores these extra keys; this loader keeps them.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from backend.config import CONFIG_DIR


class RegionRulesError(ValueError):
    """region.yaml is missing a safety table the scorers require."""


@lru_cache(maxsize=1)
def load_region_rules() -> dict[str, Any]:
    path = CONFIG_DIR / "region.yaml"
    with path.open() as handle:
        data: dict[str, Any] = yaml.safe_load(handle)
    _require_bloom_tables(data)
    return data


def clear_region_rules_cache() -> None:
    load_region_rules.cache_clear()


def _require_bloom_tables(data: dict[str, Any]) -> None:
    regions = data.get("bloom_regions")
    if not isinstance(regions, dict) or "outer_coast" not in regions or "sf_bay" not in regions:
        raise RegionRulesError("bloom_regions must define outer_coast and sf_bay")
    outer = regions["outer_coast"]
    bay = regions["sf_bay"]
    if "bloom_above_mg_m3" not in outer:
        raise RegionRulesError("outer_coast bloom threshold is missing")
    for key in ("protective_max_mg_m3", "at_risk_low_mg_m3", "at_risk_high_mg_m3"):
        if key not in bay:
            raise RegionRulesError(f"sf_bay bloom threshold {key} is missing")
