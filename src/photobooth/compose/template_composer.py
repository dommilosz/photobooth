from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

from photobooth.compose.slot_detector import Slot, clear_slot_regions, photo_rect
from photobooth.compose.svg_template import compose_svg, render_svg_to_image
from photobooth.compose.template_registry import TemplateRegistry, TemplateSpec
from photobooth.compose.utils import duplicate_strip_to_sheet, fit_photo, mm_to_px

# Cached punched overlays keyed by (template id(image), slot signature).
_OVERLAY_CACHE: dict[tuple[int, tuple], Image.Image] = {}


def _slot_sig(slots) -> tuple:
    return tuple((s.x, s.y, s.w, s.h, s.index) for s in slots)


def _punched_overlay(template: Image.Image, slots) -> Image.Image:
    key = (id(template), _slot_sig(slots))
    overlay = _OVERLAY_CACHE.get(key)
    if overlay is None:
        overlay = clear_slot_regions(template, slots)
        _OVERLAY_CACHE[key] = overlay
    return overlay


def render_template_preview(
    spec: TemplateSpec,
    photos: list[Path],
    *,
    width: int | None = None,
    height: int | None = None,
) -> Image.Image:
    """Compose template with photos for UI previews."""
    mapping = spec.meta.slot_mapping
    if spec.format == "svg":
        tw, th = spec.template_size_px()
        if width is None:
            width = tw
        if height is None:
            height = th
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            compose_svg(
                spec.template_path,
                photos,
                mapping,
                tmp_path,
                render_width=width,
                render_height=height,
            )
            return render_svg_to_image(tmp_path, width, height)
        finally:
            tmp_path.unlink(missing_ok=True)

    if not spec.image:
        raise RuntimeError("Template image not loaded")
    image = spec.image
    slots = spec.slots
    if width and height and (image.width > width or image.height > height):
        scale = min(width / image.width, height / image.height)
        nw = max(1, int(image.width * scale))
        nh = max(1, int(image.height * scale))
        image = image.resize((nw, nh), Image.BILINEAR)
        slots = [
            Slot(
                x=max(0, int(s.x * scale)),
                y=max(0, int(s.y * scale)),
                w=max(1, int(s.w * scale)),
                h=max(1, int(s.h * scale)),
                index=s.index,
            )
            for s in slots
        ]
    return _render_png_template(image, slots, mapping, photos)


def render_template_preview_legacy(
    template: Image.Image,
    slots,
    mapping: list[int],
    photos: list[Path],
) -> Image.Image:
    return _render_png_template(template, slots, mapping, photos)


def _render_png_template(
    template: Image.Image,
    slots,
    mapping: list[int],
    photos: list[Path],
) -> Image.Image:
    canvas = Image.new("RGB", template.size, (255, 255, 255))
    opened: dict[int, Image.Image] = {}
    for i, slot in enumerate(slots):
        photo_idx = mapping[i]
        if photo_idx >= len(photos):
            continue
        x, y, w, h = photo_rect(slot, template.size)
        photo = opened.get(photo_idx)
        if photo is None:
            with Image.open(photos[photo_idx]) as im:
                photo = im.convert("RGB")
            opened[photo_idx] = photo
        fitted = fit_photo(photo, w, h)
        canvas.paste(fitted, (x, y))
    overlay = _punched_overlay(template, slots)
    # Faster than alpha_composite when overlay is mostly opaque chrome.
    return Image.alpha_composite(canvas.convert("RGBA"), overlay)


def compose_sheet(
    photos: list[Path],
    registry: TemplateRegistry,
    mode_id: str,
    output: Path,
    quality: int = 90,
    dpi: int = 300,
) -> Path:
    spec = registry.load(mode_id)
    if not spec.valid:
        raise RuntimeError(spec.error or f"Template not valid: {mode_id}")
    mapping = spec.meta.slot_mapping
    if len(spec.slots) != len(mapping):
        raise RuntimeError(spec.error or "Slot count mismatch")

    print_w = mm_to_px(spec.meta.sheet_mm[0], dpi)
    print_h = mm_to_px(spec.meta.sheet_mm[1], dpi)
    strip_w, strip_h = registry.template_size_px(mode_id, dpi)

    if spec.format == "svg":
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            composed_svg = Path(tmp.name)
        try:
            compose_svg(
                spec.template_path,
                photos,
                mapping,
                composed_svg,
                render_width=strip_w,
                render_height=strip_h,
            )
            strip = render_svg_to_image(composed_svg, strip_w, strip_h)
        finally:
            composed_svg.unlink(missing_ok=True)
    else:
        if not spec.image:
            raise RuntimeError(f"Template not loaded: {mode_id}")
        strip = _render_png_template(spec.image, spec.slots, mapping, photos)

    if spec.meta.category == "strip":
        result = duplicate_strip_to_sheet(
            strip, print_w, print_h, sheet_width_mm=spec.meta.sheet_mm[0], dpi=dpi
        )
    else:
        result = strip

    output.parent.mkdir(parents=True, exist_ok=True)
    rgb = result if result.mode == "RGB" else result.convert("RGB")
    # Embed real DPI so CUPS does not assume 72 DPI (that spills one sheet onto 2+ pages).
    rgb.save(
        output,
        "JPEG",
        quality=quality,
        optimize=False,
        subsampling=2,
        dpi=(dpi, dpi),
    )
    return output
