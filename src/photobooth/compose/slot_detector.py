from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image

MARKER_COLOR = (0x88, 0xA2, 0x01)  # #88a201
ANTIALIAS_PAD = 2
PHOTO_BLEED_PX = 5  # compose photos this far past the marker edge


@dataclass
class Slot:
    x: int
    y: int
    w: int
    h: int
    index: int = 0


def _slot_mask(
    rgba: np.ndarray,
    *,
    alpha_threshold: int,
    marker_color: tuple[int, int, int],
    color_tolerance: int,
) -> np.ndarray:
    alpha = rgba[:, :, 3]
    rgb = rgba[:, :, :3]
    transparent = alpha < alpha_threshold
    target = np.array(marker_color, dtype=np.int16)
    marker = np.all(np.abs(rgb.astype(np.int16) - target) <= color_tolerance, axis=2)
    return (transparent | marker).astype(np.uint8)


def _inset_rect(
    x: int,
    y: int,
    w: int,
    h: int,
    pad: int,
    bounds: tuple[int, int],
) -> tuple[int, int, int, int] | None:
    if pad > 0:
        x += pad
        y += pad
        w -= 2 * pad
        h -= 2 * pad
    max_w, max_h = bounds
    if w <= 0 or h <= 0:
        return None
    if x < 0 or y < 0 or x + w > max_w or y + h > max_h:
        return None
    return x, y, w, h


def clear_slot_regions(
    template: Image.Image,
    slots: list[Slot] | None = None,
    *,
    alpha_threshold: int = 8,
    marker_color: tuple[int, int, int] = MARKER_COLOR,
    color_tolerance: int = 30,
    bleed_px: int = PHOTO_BLEED_PX,
) -> Image.Image:
    """Punch transparent holes for photos, including bleed past marker edges."""
    arr = np.array(template.convert("RGBA"))
    h, w = arr.shape[:2]
    mask = _slot_mask(
        arr,
        alpha_threshold=alpha_threshold,
        marker_color=marker_color,
        color_tolerance=color_tolerance,
    ).astype(bool)
    arr[mask, 3] = 0
    if slots:
        for slot in slots:
            x, y, rw, rh = photo_rect(slot, (w, h), bleed_px=bleed_px)
            arr[y : y + rh, x : x + rw, 3] = 0
    return Image.fromarray(arr, "RGBA")


def photo_rect(
    slot: Slot,
    template_size: tuple[int, int],
    *,
    antialias_pad: int = ANTIALIAS_PAD,
    bleed_px: int = PHOTO_BLEED_PX,
) -> tuple[int, int, int, int]:
    """Slot rect expanded past the marker to hide antialiased green edges."""
    tw, th = template_size
    bleed = antialias_pad + bleed_px
    x = max(0, slot.x - bleed)
    y = max(0, slot.y - bleed)
    w = min(tw - x, slot.w + 2 * bleed)
    h = min(th - y, slot.h + 2 * bleed)
    return x, y, w, h


def detect_slots(
    template: Image.Image,
    alpha_threshold: int = 8,
    min_size: int = 50,
    min_area: int = 1000,
    antialias_pad: int = 2,
    marker_color: tuple[int, int, int] = MARKER_COLOR,
    color_tolerance: int = 30,
    *,
    column_first: bool = False,
) -> list[Slot]:
    rgba = np.array(template.convert("RGBA"))
    mask = _slot_mask(
        rgba,
        alpha_threshold=alpha_threshold,
        marker_color=marker_color,
        color_tolerance=color_tolerance,
    )
    h, w = mask.shape

    scale = 1.0
    max_dim = 800
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        mask = cv2.resize(
            mask,
            (int(w * scale), int(h * scale)),
            interpolation=cv2.INTER_NEAREST,
        )

    mh, mw = mask.shape
    min_px = max(4, int(min_size * scale))
    min_area_px = max(1, int(min_area * scale * scale))
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=4)
    components: list[tuple[int, int, int, int]] = []
    for i in range(1, stats.shape[0]):
        x, y, bw, bh, area = (
            int(stats[i, cv2.CC_STAT_LEFT]),
            int(stats[i, cv2.CC_STAT_TOP]),
            int(stats[i, cv2.CC_STAT_WIDTH]),
            int(stats[i, cv2.CC_STAT_HEIGHT]),
            int(stats[i, cv2.CC_STAT_AREA]),
        )
        if bw < min_px or bh < min_px or area < min_area_px:
            continue
        if area / (bw * bh) < 0.95:
            continue
        if scale != 1.0:
            x = int(x / scale)
            y = int(y / scale)
            bw = int(bw / scale)
            bh = int(bh / scale)
        inset = _inset_rect(x, y, bw, bh, antialias_pad, (w, h))
        if inset is None:
            continue
        x, y, bw, bh = inset
        if bw < min_size or bh < min_size or bw * bh < min_area:
            continue
        components.append((x, y, bw, bh))

    row_tol = max(20, h // 30)
    col_tol = max(20, w // 30)
    if column_first or w > h:
        components.sort(key=lambda r: (r[0] // col_tol, r[1]))
    else:
        components.sort(key=lambda r: (r[1] // row_tol, r[0]))
    return [Slot(x=x, y=y, w=bw, h=bh, index=i) for i, (x, y, bw, bh) in enumerate(components)]
