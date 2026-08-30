from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image

from photobooth.paths import app_root

SAMPLE_PHOTO_NAMES = ("random-person.jpg", "random-person.jpeg", "random-person.png")


def resolve_sample_photo_path() -> Path | None:
    assets = app_root() / "assets"
    for name in SAMPLE_PHOTO_NAMES:
        path = assets / name
        if path.is_file():
            return path
    return None


@lru_cache(maxsize=1)
def sample_photo_path() -> Path | None:
    return resolve_sample_photo_path()


@lru_cache(maxsize=1)
def load_sample_photo() -> Image.Image | None:
    path = sample_photo_path()
    if not path:
        return None
    with Image.open(path) as img:
        return img.convert("RGB")


def ensure_sample_photo_file() -> Path | None:
    source = sample_photo_path()
    if source is None:
        return None
    path = app_root() / "data" / "sample-preview.jpg"
    if not path.is_file() or path.stat().st_mtime < source.stat().st_mtime:
        path.parent.mkdir(parents=True, exist_ok=True)
        photo = load_sample_photo()
        if photo is None:
            return None
        photo.save(path, quality=90)
    return path


def sample_photo_paths(count: int) -> list[Path]:
    path = ensure_sample_photo_file()
    if path is None or count < 1:
        return []
    return [path] * count
