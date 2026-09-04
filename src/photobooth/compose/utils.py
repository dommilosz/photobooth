from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw


def fit_photo(photo: Image.Image, width: int, height: int) -> Image.Image:
    """Cover-fit photo into width×height (center-crop). Uses OpenCV for speed on Pi."""
    if photo.mode != "RGB":
        photo = photo.convert("RGB")
    src = np.asarray(photo)
    sh, sw = src.shape[:2]
    if sw < 1 or sh < 1 or width < 1 or height < 1:
        return Image.new("RGB", (max(1, width), max(1, height)), (0, 0, 0))

    scale = max(width / sw, height / sh)
    nw = max(1, int(sw * scale + 0.5))
    nh = max(1, int(sh * scale + 0.5))
    if nw != sw or nh != sh:
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        src = cv2.resize(src, (nw, nh), interpolation=interp)
        sh, sw = src.shape[:2]

    left = max(0, (sw - width) // 2)
    top = max(0, (sh - height) // 2)
    cropped = src[top : top + height, left : left + width]
    if cropped.shape[0] != height or cropped.shape[1] != width:
        # Clamp edge cases from rounding
        out = np.zeros((height, width, 3), dtype=np.uint8)
        h = min(height, cropped.shape[0])
        w = min(width, cropped.shape[1])
        out[:h, :w] = cropped[:h, :w]
        cropped = out
    return Image.fromarray(cropped)


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
        return strip if strip.mode == "RGB" else strip.convert("RGB")

    arr = np.asarray(strip.convert("RGB"))
    sh, sw = arr.shape[:2]
    if sh != column_h:
        scale = column_h / sh
        nw = max(1, int(round(sw * scale)))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        arr = cv2.resize(arr, (nw, column_h), interpolation=interp)
        sh, sw = arr.shape[:2]

    if sw == column_w:
        return Image.fromarray(arr)
    if sw > column_w:
        left = (sw - column_w) // 2
        return Image.fromarray(arr[:, left : left + column_w])

    canvas = np.zeros((column_h, column_w, 3), dtype=np.uint8)
    x0 = (column_w - sw) // 2
    canvas[:, x0 : x0 + sw] = arr
    if x0 > 0:
        canvas[:, :x0] = arr[:, :1]
    if x0 + sw < column_w:
        canvas[:, x0 + sw :] = arr[:, -1:]
    return Image.fromarray(canvas)


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
    sheet = Image.new("RGB", (print_width, print_height), (255, 255, 255))
    sheet.paste(left, (0, 0))
    sheet.paste(right, (col1_w, 0))
    _draw_strip_cut_line(sheet, col1_w, dpi=dpi)
    return sheet
