from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from photobooth.paths import app_root, config_path


def load_config(path: Path | None = None) -> dict[str, Any]:
    p = path or config_path()
    with p.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("paths", {})
    return cfg


def save_config(cfg: dict[str, Any], path: Path | None = None) -> None:
    p = path or config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)


def resolve_templates_dir(cfg: dict[str, Any]) -> Path:
    rel = cfg.get("layout", {}).get("templates_dir", "templates")
    p = Path(rel)
    if not p.is_absolute():
        p = app_root() / p
    return p


def update_config(mutator) -> dict[str, Any]:
    cfg = load_config()
    mutator(cfg)
    save_config(cfg)
    return cfg
