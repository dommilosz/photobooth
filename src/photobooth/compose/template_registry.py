from __future__ import annotations

import logging
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from PIL import Image

from photobooth.compose.slot_detector import Slot, detect_slots
from photobooth.compose.svg_template import (
    compose_svg,
    detect_svg_category,
    detect_svg_slots,
    parse_viewbox,
    render_svg_to_image,
)
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
    template_path: Path
    format: str  # "png" or "svg"
    meta: TemplateMeta
    slots: list[Slot] = field(default_factory=list)
    image: Image.Image | None = None
    valid: bool = True
    error: str = ""
    inferred: bool = False

    @property
    def capture_count(self) -> int:
        return self.meta.capture_count

    def template_size_px(self, dpi: int = 300) -> tuple[int, int]:
        w_mm, h_mm = self.meta.sheet_mm
        if self.meta.category == "strip":
            return mm_to_px(w_mm / 2, dpi), mm_to_px(h_mm, dpi)
        return mm_to_px(w_mm, dpi), mm_to_px(h_mm, dpi)

    @property
    def png_path(self) -> Path:
        """Backwards-compatible alias."""
        return self.template_path


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


def cups_media_for_sheet(sheet_mm: list[int] | tuple[int, ...] | None = None) -> str:
    """CUPS media for the full print sheet. Selphy dye-subs typically only expose Postcard."""
    del sheet_mm  # reserved for future size-specific mapping
    return "Postcard"


def _infer_meta(mode_id: str, category: str, slots: list[Slot]) -> TemplateMeta:
    count = len(slots)
    sheet_mm = list(DEFAULT_SHEET_MM)
    return TemplateMeta(
        name=_title_from_mode_id(mode_id),
        capture_count=count,
        slot_mapping=list(range(count)),
        sheet_mm=sheet_mm,
        cups_media=cups_media_for_sheet(sheet_mm),
        category=category,
    )


def _meta_from_yaml(raw: dict, mode_id: str, category: str) -> TemplateMeta:
    sheet_mm = list(raw.get("sheet_mm", DEFAULT_SHEET_MM))
    cups_media = (raw.get("cups_media") or "").strip()
    # Half-strip / custom sizes are not usable on Selphy — force Postcard.
    if not cups_media or cups_media in {
        "w192h288",
        "w288h192",
        "Custom.100x150mm",
        "Custom.150x100mm",
    }:
        cups_media = cups_media_for_sheet(sheet_mm)
    return TemplateMeta(
        name=raw.get("name", _title_from_mode_id(mode_id)),
        capture_count=int(raw.get("capture_count", 0)),
        slot_mapping=list(raw.get("slot_mapping", [])),
        sheet_mm=sheet_mm,
        cups_media=cups_media,
        category=raw.get("category") or category,
    )


def _resolve_template_path(template_dir: Path, mode_id: str) -> tuple[Path, str] | None:
    png = template_dir / f"{mode_id}.png"
    svg = template_dir / f"{mode_id}.svg"
    if png.exists():
        return png, "png"
    if svg.exists():
        return svg, "svg"
    return None


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
        for path in self._dir.glob("*.png"):
            mode_ids.add(path.stem)
        for path in self._dir.glob("*.svg"):
            mode_ids.add(path.stem)
        return [self.load(mode_id) for mode_id in sorted(mode_ids)]

    def load(self, mode_id: str) -> TemplateSpec:
        if mode_id in self._cache:
            return self._cache[mode_id]

        resolved = _resolve_template_path(self._dir, mode_id)
        meta_path = self._dir / f"{mode_id}.meta.yaml"
        if resolved is None:
            missing = self._dir / f"{mode_id}.png"
            spec = TemplateSpec(
                mode_id=mode_id,
                template_path=missing,
                format="png",
                meta=TemplateMeta("?", 0, [], [0, 0]),
                valid=False,
                error="Missing template file (PNG or SVG)",
            )
            self._cache[mode_id] = spec
            return spec

        template_path, fmt = resolved
        inferred = not meta_path.exists()

        if fmt == "svg":
            category = detect_svg_category(template_path)
            slots = detect_svg_slots(template_path, column_first=(category == "strip"))
            image = None
        else:
            image = Image.open(template_path).convert("RGBA")
            category = detect_category(image)
            slots = detect_slots(image, column_first=(category == "strip"))

        if inferred:
            meta = _infer_meta(mode_id, category, slots)
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
            if fmt == "svg" and not raw.get("category"):
                category = detect_svg_category(template_path, sheet_mm=list(raw.get("sheet_mm", DEFAULT_SHEET_MM)))
            elif fmt == "png" and not raw.get("category"):
                category = detect_category(image, sheet_mm=list(raw.get("sheet_mm", DEFAULT_SHEET_MM)))
            meta = _meta_from_yaml(raw, mode_id, category)
            if fmt == "svg":
                slots = detect_svg_slots(template_path, column_first=(meta.category == "strip"))
            else:
                slots = detect_slots(image, column_first=(meta.category == "strip"))
            valid = True
            error = ""
            if len(slots) != len(meta.slot_mapping):
                valid = False
                error = f"Expected {len(meta.slot_mapping)} slots, detected {len(slots)}"
                log.warning("Template %s: %s", mode_id, error)

        spec = TemplateSpec(
            mode_id=mode_id,
            template_path=template_path,
            format=fmt,
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

    def template_size_px(self, mode_id: str, dpi: int = DEFAULT_DPI) -> tuple[int, int]:
        return self.load(mode_id).template_size_px(dpi)

    def viewbox_size(self, mode_id: str) -> tuple[float, float]:
        spec = self.load(mode_id)
        if spec.format != "svg":
            if spec.image:
                return float(spec.image.width), float(spec.image.height)
            return 0.0, 0.0
        _, _, w, h = parse_viewbox(spec.template_path)
        return w, h
