from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw


def fit_photo(photo: Image.Image, width: int, height: int) -> Image.Image:
    src = photo.convert("RGB")
    sw, sh = src.size
    scale = max(width / sw, height / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    resized = src.resize((nw, nh), Image.Resampling.LANCZOS)
    left = (nw - width) // 2
    top = (nh - height) // 2
    return resized.crop((left, top, left + width, top + height))


def mm_to_px(mm: float, dpi: int = 300) -> int:
    return int(round(mm / 25.4 * dpi))


def strip_column_widths(
    print_width: int,
    sheet_width_mm: float = 100,
    dpi: int = 300,
) -> tuple[int, int]:
    """Pixel widths for two 5 cm strips on a 10 cm sheet (may differ by 1 px)."""
    left = mm_to_px(sheet_width_mm / 2, dpi)
    if left * 2 > print_width:
        left = print_width // 2
    return left, print_width - left


def _fit_strip_to_column(strip: Image.Image, column_w: int, column_h: int) -> Image.Image:
    """Fit a strip template into a print column without squashing."""
    if strip.size == (column_w, column_h):
        return strip
    sw, sh = strip.size
    if sh != column_h:
        scale = column_h / sh
        strip = strip.resize((int(round(sw * scale)), column_h), Image.Resampling.LANCZOS)
        sw = strip.width
    if sw == column_w:
        return strip
    if sw > column_w:
        left = (sw - column_w) // 2
        return strip.crop((left, 0, left + column_w, column_h))
    arr = np.array(strip.convert("RGBA"))
    canvas = np.zeros((column_h, column_w, 4), dtype=np.uint8)
    x0 = (column_w - sw) // 2
    canvas[:, x0 : x0 + sw] = arr
    if x0 > 0:
        canvas[:, :x0] = arr[:, :1]
    if x0 + sw < column_w:
        canvas[:, x0 + sw :] = arr[:, -1:]
    return Image.fromarray(canvas, "RGBA")


def _draw_dashed_vline(
    draw: ImageDraw.ImageDraw,
    x: int,
    y0: int,
    y1: int,
    *,
    color: tuple[int, int, int] = (90, 90, 90),
    width: int = 1,
    dash: int = 10,
    gap: int = 8,
) -> None:
    y = y0
    while y < y1:
        y_end = min(y + dash, y1)
        draw.line([(x, y), (x, y_end)], fill=color, width=width)
        y += dash + gap


def _draw_strip_cut_line(sheet: Image.Image, cut_x: int, *, dpi: int = 300) -> None:
    """Dashed vertical guide on the join between mirrored strips."""
    draw = ImageDraw.Draw(sheet)
    margin = mm_to_px(4, dpi)
    _draw_dashed_vline(draw, cut_x, margin, sheet.height - margin)


def duplicate_strip_to_sheet(
    strip: Image.Image,
    print_width: int,
    print_height: int,
    *,
    sheet_width_mm: float = 100,
    dpi: int = 300,
) -> Image.Image:
    """Tile two 5×15 cm strips edge-to-edge on a 10×15 cm sheet."""
    col1_w, col2_w = strip_column_widths(print_width, sheet_width_mm, dpi)
    left = _fit_strip_to_column(strip, col1_w, print_height)
    right = _fit_strip_to_column(strip, col2_w, print_height)
    sheet = Image.new("RGBA", (print_width, print_height), (255, 255, 255, 255))
    sheet.paste(left.convert("RGB"), (0, 0))
    sheet.paste(right.convert("RGB"), (col1_w, 0))
    _draw_strip_cut_line(sheet, col1_w, dpi=dpi)
    return sheet
