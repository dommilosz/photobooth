from __future__ import annotations

from pathlib import Path


def app_root() -> Path:
    """Project root (parent of src/photobooth when running from source)."""
    return Path(__file__).resolve().parents[2]


def config_path() -> Path:
    return app_root() / "config" / "default.yaml"


def templates_dir() -> Path:
    return app_root() / "templates"


def ensure_data_dirs(cfg: dict) -> None:
    root = app_root()
    for key in ("data_dir", "prints_dir", "sessions_dir", "upload_queue_dir"):
        rel = cfg.get("paths", {}).get(key, f"data/{key}")
        (root / rel).mkdir(parents=True, exist_ok=True)
