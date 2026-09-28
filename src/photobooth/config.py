from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from photobooth.paths import app_root, config_path, local_config_path


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load config.

    - Explicit ``path`` / ``--config``: that file only.
    - Default: ``config/default.yaml`` merged with ``config/local.yaml``
      (local wins). Machine-specific settings belong in local.yaml.
    """
    if path is not None:
        cfg = _read_yaml(path)
        cfg.setdefault("paths", {})
        return cfg

    defaults = _read_yaml(config_path())
    local = _read_yaml(local_config_path())
    cfg = _deep_merge(defaults, local) if local else defaults
    cfg.setdefault("paths", {})
    return cfg


def save_config(cfg: dict[str, Any], path: Path | None = None) -> None:
    """Persist config.

    Without an explicit path, writes ``config/local.yaml`` so git-tracked
    ``default.yaml`` is never overwritten by the UI.
    """
    p = path or local_config_path()
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
