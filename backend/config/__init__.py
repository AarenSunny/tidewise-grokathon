"""YAML config loaders for region and activity scorers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from backend.models.spots import RegionConfig

CONFIG_DIR = Path(__file__).resolve().parent


def load_region(path: Path | None = None) -> RegionConfig:
    cfg_path = path or (CONFIG_DIR / "region.yaml")
    with cfg_path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)
    return RegionConfig.model_validate(data)


def load_activity_config(activity: str) -> dict[str, Any]:
    cfg_path = CONFIG_DIR / "activities" / f"{activity}.yaml"
    with cfg_path.open() as f:
        return yaml.safe_load(f)
