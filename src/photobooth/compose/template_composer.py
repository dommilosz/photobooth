from __future__ import annotations

from pathlib import Path

from PIL import Image

from photobooth.compose.slot_detector import clear_slot_regions, photo_rect
from photobooth.compose.template_registry import TemplateRegistry
from photobooth.compose.utils import duplicate_strip_to_sheet, fit_photo, mm_to_px


def render_template_preview(
    template: Image.Image,
    slots,
    mapping: list[int],
    photos: list[Path],
) -> Image.Image:
    """Compose template with photos for UI previews."""
    return _render_template(template, slots, mapping, photos)


def _render_template(
    template: Image.Image,
    slots,
    mapping: list[int],
    photos: list[Path],
) -> Image.Image:
    canvas = Image.new("RGB", template.size, (255, 255, 255))
    for i, slot in enumerate(slots):
        photo_idx = mapping[i]
        if photo_idx >= len(photos):
            continue
        x, y, w, h = photo_rect(slot, template.size)
        photo = Image.open(photos[photo_idx])
        fitted = fit_photo(photo, w, h)
        canvas.paste(fitted, (x, y))
    overlay = clear_slot_regions(template, slots)
    return Image.alpha_composite(canvas.convert("RGBA"), overlay)


def compose_sheet(
    photos: list[Path],
    registry: TemplateRegistry,
    mode_id: str,
    output: Path,
    quality: int = 95,
    dpi: int = 300,
) -> Path:
    spec = registry.load(mode_id)
    if not spec.image:
        raise RuntimeError(f"Template not loaded: {mode_id}")
    mapping = spec.meta.slot_mapping
    if len(spec.slots) != len(mapping):
        raise RuntimeError(spec.error or "Slot count mismatch")

    strip = _render_template(spec.image, spec.slots, mapping, photos)
    if spec.meta.category == "strip":
        print_w = mm_to_px(spec.meta.sheet_mm[0], dpi)
        print_h = mm_to_px(spec.meta.sheet_mm[1], dpi)
        result = duplicate_strip_to_sheet(
            strip, print_w, print_h, sheet_width_mm=spec.meta.sheet_mm[0], dpi=dpi
        )
    else:
        result = strip

    output.parent.mkdir(parents=True, exist_ok=True)
    result.convert("RGB").save(output, "JPEG", quality=quality)
    return output
