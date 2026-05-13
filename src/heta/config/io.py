"""YAML configuration IO for Little Heta."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from heta.config.schema import HetaConfig

CONFIG_DIR = Path.home() / ".heta"
CONFIG_PATH = CONFIG_DIR / "heta.yaml"


def load_config(path: Path | None = None) -> HetaConfig | None:
    """Load Little Heta config, returning None when the config file does not exist."""
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        return None

    with config_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid config file: {config_path}")
    return HetaConfig.from_dict(data)


def save_config(config: HetaConfig | dict[str, Any], path: Path | None = None) -> Path:
    """Save Little Heta config to YAML and create the parent directory if needed."""
    config_path = path or CONFIG_PATH
    config_path.parent.mkdir(parents=True, exist_ok=True)

    data = config.to_dict() if isinstance(config, HetaConfig) else config
    with config_path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(data, file, sort_keys=False, allow_unicode=True)
    return config_path

