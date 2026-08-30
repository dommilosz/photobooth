from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from PIL import Image

from photobooth.compose.slot_detector import Slot, detect_slots
from photobooth.compose.utils import mm_to_px
from photobooth.config import resolve_templates_dir

log = logging.getLogger(__name__)

DEFAULT_SHEET_MM = [100, 150]
DEFAULT_DPI = 300


@dataclass
class TemplateMeta:
    name: str
    capture_count: int
    slot_mapping: list[int]
    sheet_mm: list[int]
    cups_media: str = ""
    category: str = "strip"


@dataclass
class TemplateSpec:
    mode_id: str
    png_path: Path
    meta: TemplateMeta
    slots: list[Slot] = field(default_factory=list)
    image: Image.Image | None = None
    valid: bool = True
    error: str = ""
    inferred: bool = False

    @property
    def capture_count(self) -> int:
        return self.meta.capture_count


def detect_category(
    image: Image.Image,
    sheet_mm: list[int] | None = None,
    dpi: int = DEFAULT_DPI,
) -> str:
    """Guess strip vs full from template width relative to a 10×15 cm sheet."""
    sheet = sheet_mm or DEFAULT_SHEET_MM
    sheet_w_mm = float(sheet[0])
    full_w = mm_to_px(sheet_w_mm, dpi)
    strip_w = mm_to_px(sheet_w_mm / 2, dpi)
    w = image.width
    if abs(w - strip_w) <= abs(w - full_w):
        return "strip"
    return "full"


def _title_from_mode_id(mode_id: str) -> str:
    return re.sub(r"\s+", " ", mode_id.replace("_", " ")).strip().title()


def _infer_meta(mode_id: str, image: Image.Image, slots: list[Slot]) -> TemplateMeta:
    category = detect_category(image)
    count = len(slots)
    return TemplateMeta(
        name=_title_from_mode_id(mode_id),
        capture_count=count,
        slot_mapping=list(range(count)),
        sheet_mm=list(DEFAULT_SHEET_MM),
        category=category,
    )


def _meta_from_yaml(raw: dict, mode_id: str, image: Image.Image) -> TemplateMeta:
    sheet_mm = list(raw.get("sheet_mm", DEFAULT_SHEET_MM))
    category = raw.get("category")
    if not category:
        category = detect_category(image, sheet_mm=sheet_mm)
    return TemplateMeta(
        name=raw.get("name", _title_from_mode_id(mode_id)),
        capture_count=int(raw.get("capture_count", 0)),
        slot_mapping=list(raw.get("slot_mapping", [])),
        sheet_mm=sheet_mm,
        cups_media=raw.get("cups_media", ""),
        category=category,
    )


class TemplateRegistry:
    def __init__(self, cfg: dict) -> None:
        self._dir = resolve_templates_dir(cfg)
        self._cache: dict[str, TemplateSpec] = {}

    def rescan(self) -> None:
        self._cache.clear()

    def list_modes(self) -> list[TemplateSpec]:
        mode_ids: set[str] = set()
        for meta_path in self._dir.glob("*.meta.yaml"):
            mode_ids.add(meta_path.name.replace(".meta.yaml", ""))
        for png_path in self._dir.glob("*.png"):
            mode_ids.add(png_path.stem)
        return [self.load(mode_id) for mode_id in sorted(mode_ids)]

    def load(self, mode_id: str) -> TemplateSpec:
        if mode_id in self._cache:
            return self._cache[mode_id]
        png = self._dir / f"{mode_id}.png"
        meta_path = self._dir / f"{mode_id}.meta.yaml"
        if not png.exists():
            spec = TemplateSpec(
                mode_id=mode_id,
                png_path=png,
                meta=TemplateMeta("?", 0, [], [0, 0]),
                valid=False,
                error="Missing template PNG",
            )
            self._cache[mode_id] = spec
            return spec

        image = Image.open(png).convert("RGBA")
        inferred = not meta_path.exists()

        if inferred:
            category = detect_category(image)
            slots = detect_slots(image, column_first=(category == "strip"))
            meta = _infer_meta(mode_id, image, slots)
            valid = len(slots) > 0
            error = "" if valid else "No slots detected"
            if valid:
                log.info(
                    "Template %s: inferred category=%s, %d slot(s)",
                    mode_id,
                    meta.category,
                    len(slots),
                )
        else:
            with meta_path.open(encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            meta = _meta_from_yaml(raw, mode_id, image)
            if not raw.get("category"):
                log.info("Template %s: inferred category=%s from PNG size", mode_id, meta.category)
            slots = detect_slots(image, column_first=(meta.category == "strip"))
            valid = True
            error = ""
            if len(slots) != len(meta.slot_mapping):
                valid = False
                error = f"Expected {len(meta.slot_mapping)} slots, detected {len(slots)}"
                log.warning("Template %s: %s", mode_id, error)

        spec = TemplateSpec(
            mode_id=mode_id,
            png_path=png,
            meta=meta,
            slots=slots,
            image=image,
            valid=valid,
            error=error,
            inferred=inferred,
        )
        self._cache[mode_id] = spec
        return spec

    def photo_count(self, mode_id: str) -> int:
        return self.load(mode_id).capture_count

    def sheet_size_px(self, mode_id: str, dpi: int = DEFAULT_DPI) -> tuple[int, int]:
        spec = self.load(mode_id)
        w_mm, h_mm = spec.meta.sheet_mm
        return int(w_mm / 25.4 * dpi), int(h_mm / 25.4 * dpi)
