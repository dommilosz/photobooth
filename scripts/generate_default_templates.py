#!/usr/bin/env python3
"""Generate default PNG templates with transparent photo slots."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


def mm(dpi: int, mm_val: float) -> int:
    return int(round(mm_val / 25.4 * dpi))


def strip_column_width(dpi: int, sheet_width_mm: float = 100) -> int:
    """Width of one 5 cm strip (half of a 10 cm print sheet)."""
    return mm(dpi, sheet_width_mm / 2)


def fit_aspect_rect(
    area_x: int,
    area_y: int,
    area_w: int,
    area_h: int,
    aspect_w: int = 4,
    aspect_h: int = 3,
) -> tuple[int, int, int, int]:
    """Largest aspect-ratio rect centered inside an area (x0, y0, x1, y1)."""
    sw = area_w
    sh = int(sw * aspect_h / aspect_w)
    if sh > area_h:
        sh = area_h
        sw = int(sh * aspect_w / aspect_h)
    x0 = area_x + (area_w - sw) // 2
    y0 = area_y + (area_h - sh) // 2
    return (x0, y0, x0 + sw, y0 + sh)


def clear_rect(img: Image.Image, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    region = img.crop(box)
    arr = np.array(region)
    arr[:, :, 3] = 0
    img.paste(Image.fromarray(arr, "RGBA"), box)


def draw_frame(img: Image.Image, margin: int = 20) -> None:
    draw = ImageDraw.Draw(img)
    w, h = img.size
    draw.rectangle([margin, margin, w - margin, h - margin], outline=(30, 30, 30, 255), width=4)
    draw.text((margin + 8, margin + 8), "PHOTOBOOTH", fill=(50, 50, 50, 255))


def strip_layout(img: Image.Image, dpi: int, photos_per_strip: int) -> None:
    """Single strip column; photos stacked along 15 cm height."""
    w, h = img.size
    gap = mm(dpi, 2)
    inner_w = w - 2 * gap
    band_h = (h - (photos_per_strip + 1) * gap) // photos_per_strip
    for i in range(photos_per_strip):
        band_y = gap + i * (band_h + gap)
        clear_rect(img, fit_aspect_rect(gap, band_y, inner_w, band_h))


def make_strip(dpi: int, photos_per_strip: int) -> Image.Image:
    w = strip_column_width(dpi)
    h = mm(dpi, 150)
    img = Image.new("RGBA", (w, h), (245, 245, 240, 255))
    draw_frame(img, margin=min(16, w // 8))
    strip_layout(img, dpi, photos_per_strip)
    return img


def strip_4_classic(dpi: int = 300) -> Image.Image:
    return make_strip(dpi, 4)


def strip_3_large(dpi: int = 300) -> Image.Image:
    return make_strip(dpi, 3)


def full_grid_4(dpi: int = 300) -> Image.Image:
    w, h = mm(dpi, 100), mm(dpi, 150)
    img = Image.new("RGBA", (w, h), (245, 245, 240, 255))
    draw_frame(img)
    gap = mm(dpi, 3)
    cell_w = (w - 3 * gap) // 2
    cell_h = (h - 3 * gap) // 2
    for row in range(2):
        for col in range(2):
            x = gap + col * (cell_w + gap)
            y = gap + row * (cell_h + gap)
            clear_rect(img, fit_aspect_rect(x, y, cell_w, cell_h))
    return img


def full_1_plus_2(dpi: int = 300) -> Image.Image:
    w, h = mm(dpi, 100), mm(dpi, 150)
    img = Image.new("RGBA", (w, h), (245, 245, 240, 255))
    draw_frame(img)
    gap = mm(dpi, 3)
    hero_band_h = int(h * 0.62) - gap
    clear_rect(img, fit_aspect_rect(gap, gap, w - 2 * gap, hero_band_h))
    small_band_h = h - hero_band_h - 3 * gap
    sw = (w - 3 * gap) // 2
    y = hero_band_h + 2 * gap
    clear_rect(img, fit_aspect_rect(gap, y, sw, small_band_h))
    clear_rect(img, fit_aspect_rect(gap + sw + gap, y, sw, small_band_h))
    return img


META = {
    "strip_4_classic": {
        "name": "4 Classic",
        "capture_count": 4,
        "slot_mapping": [0, 1, 2, 3],
        "sheet_mm": [100, 150],
        "cups_media": "w192h288",
        "category": "strip",
    },
    "strip_3_large": {
        "name": "3 Larger",
        "capture_count": 3,
        "slot_mapping": [0, 1, 2],
        "sheet_mm": [100, 150],
        "cups_media": "w192h288",
        "category": "strip",
    },
    "full_grid_4": {
        "name": "4 Grid",
        "capture_count": 4,
        "slot_mapping": [0, 1, 2, 3],
        "sheet_mm": [100, 150],
        "cups_media": "w192h288",
        "category": "full",
    },
    "full_1_plus_2": {
        "name": "1 + 2 Below",
        "capture_count": 3,
        "slot_mapping": [0, 1, 2],
        "sheet_mm": [100, 150],
        "cups_media": "w192h288",
        "category": "full",
    },
}


def main() -> None:
    import yaml

    TEMPLATES.mkdir(parents=True, exist_ok=True)
    gens = {
        "strip_4_classic": strip_4_classic,
        "strip_3_large": strip_3_large,
        "full_grid_4": full_grid_4,
        "full_1_plus_2": full_1_plus_2,
    }
    for name, fn in gens.items():
        img = fn()
        png = TEMPLATES / f"{name}.png"
        img.save(png)
        meta_path = TEMPLATES / f"{name}.meta.yaml"
        with meta_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(META[name], f, sort_keys=False)
        print(f"Wrote {png} ({img.size[0]}x{img.size[1]}) and {meta_path}")


if __name__ == "__main__":
    main()
