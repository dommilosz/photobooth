from __future__ import annotations

import base64
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from photobooth.compose.slot_detector import MARKER_COLOR, Slot
from photobooth.compose.utils import fit_photo

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

_MARKER_RGB = MARKER_COLOR
_MARKER_HEX = "#88a201"


@dataclass(frozen=True)
class BBox:
    x: float
    y: float
    w: float
    h: float


def parse_viewbox(svg_path: Path) -> tuple[float, float, float, float]:
    root = ET.parse(svg_path).getroot()
    vb = root.get("viewBox")
    if vb:
        parts = [float(v) for v in vb.replace(",", " ").split()]
        if len(parts) == 4:
            return parts[0], parts[1], parts[2], parts[3]
    width = _length(root.get("width", "0"))
    height = _length(root.get("height", "0"))
    return 0.0, 0.0, width, height


def _length(value: str) -> float:
    return float(re.sub(r"[a-zA-Z%]+$", "", value.strip()) or 0)


def _parse_hex_color(value: str) -> tuple[int, int, int] | None:
    value = value.strip().lower()
    if value.startswith("#"):
        h = value[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 6:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return None


def _parse_fill(elem: ET.Element) -> str | None:
    fill = elem.get("fill")
    if fill:
        return fill
    style = elem.get("style", "")
    m = re.search(r"fill\s*:\s*([^;]+)", style, re.I)
    return m.group(1).strip() if m else None


def _is_marker_fill(fill: str | None) -> bool:
    if not fill:
        return False
    fill = fill.strip().lower()
    if fill in ("none", "transparent"):
        return False
    rgb = _parse_hex_color(fill)
    if rgb is None:
        return False
    return all(abs(rgb[i] - _MARKER_RGB[i]) <= 30 for i in range(3))


def _parse_matrix(transform: str) -> tuple[float, float, float, float, float, float]:
    transform = transform.strip()
    if transform.startswith("matrix("):
        nums = [float(n) for n in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", transform)]
        if len(nums) == 6:
            return tuple(nums)  # type: ignore[return-value]
    if transform.startswith("translate("):
        nums = [float(n) for n in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", transform)]
        tx = nums[0] if nums else 0.0
        ty = nums[1] if len(nums) > 1 else 0.0
        return 1.0, 0.0, 0.0, 1.0, tx, ty
    return 1.0, 0.0, 0.0, 1.0, 0.0, 0.0


def _multiply(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
) -> tuple[float, float, float, float, float, float]:
    a1, b1, c1, d1, e1, f1 = a
    a2, b2, c2, d2, e2, f2 = b
    return (
        a1 * a2 + c1 * b2,
        b1 * a2 + d1 * b2,
        a1 * c2 + c1 * d2,
        b1 * c2 + d1 * d2,
        a1 * e2 + c1 * f2 + e1,
        b1 * e2 + d1 * f2 + f1,
    )


def _apply_matrix(
    x: float, y: float, m: tuple[float, float, float, float, float, float]
) -> tuple[float, float]:
    a, b, c, d, e, f = m
    return a * x + c * y + e, b * x + d * y + f


def _transform_bbox(bbox: BBox, m: tuple[float, float, float, float, float, float]) -> BBox:
    corners = [
        _apply_matrix(bbox.x, bbox.y, m),
        _apply_matrix(bbox.x + bbox.w, bbox.y, m),
        _apply_matrix(bbox.x, bbox.y + bbox.h, m),
        _apply_matrix(bbox.x + bbox.w, bbox.y + bbox.h, m),
    ]
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    return BBox(x0, y0, x1 - x0, y1 - y0)


def _path_bbox(d: str) -> BBox | None:
    nums = [float(n) for n in re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", d)]
    if len(nums) < 4:
        return None
    xs = nums[0::2]
    ys = nums[1::2]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if x1 <= x0 or y1 <= y0:
        return None
    return BBox(x0, y0, x1 - x0, y1 - y0)


def _element_bbox(elem: ET.Element) -> BBox | None:
    tag = elem.tag.rsplit("}", 1)[-1]
    if tag == "rect":
        return BBox(
            _length(elem.get("x", "0")),
            _length(elem.get("y", "0")),
            _length(elem.get("width", "0")),
            _length(elem.get("height", "0")),
        )
    if tag == "path":
        d = elem.get("d", "")
        return _path_bbox(d)
    return None


def _find_markers(
    root: ET.Element,
    *,
    column_first: bool = False,
) -> list[tuple[ET.Element, BBox, BBox]]:
    """Return (element, world_bbox, local_bbox) for each green marker."""
    found: list[tuple[ET.Element, BBox, BBox]] = []
    identity = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    def walk(elem: ET.Element, matrix: tuple[float, float, float, float, float, float]) -> None:
        local = identity
        transform = elem.get("transform")
        if transform:
            local = _parse_matrix(transform)
        combined = _multiply(matrix, local)
        if _is_marker_fill(_parse_fill(elem)):
            local_bbox = _element_bbox(elem)
            if local_bbox and local_bbox.w > 0 and local_bbox.h > 0:
                found.append((elem, _transform_bbox(local_bbox, combined), local_bbox))
        for child in list(elem):
            walk(child, combined)

    walk(root, identity)
    _, _, vb_w, vb_h = parse_viewbox_from_root(root)
    row_tol = max(1.0, vb_h / 30)
    col_tol = max(1.0, vb_w / 30)
    if column_first or vb_w > vb_h:
        found.sort(key=lambda item: (item[1].x // col_tol, item[1].y))
    else:
        found.sort(key=lambda item: (item[1].y // row_tol, item[1].x))
    return found


def parse_viewbox_from_root(root: ET.Element) -> tuple[float, float, float, float]:
    vb = root.get("viewBox")
    if vb:
        parts = [float(v) for v in vb.replace(",", " ").split()]
        if len(parts) == 4:
            return parts[0], parts[1], parts[2], parts[3]
    return 0.0, 0.0, _length(root.get("width", "0")), _length(root.get("height", "0"))


def detect_svg_slots(svg_path: Path, *, column_first: bool = False) -> list[Slot]:
    root = ET.parse(svg_path).getroot()
    markers = _find_markers(root, column_first=column_first)
    return [
        Slot(x=int(round(world.x)), y=int(round(world.y)), w=int(round(world.w)), h=int(round(world.h)), index=i)
        for i, (_, world, _) in enumerate(markers)
    ]


def detect_svg_category(svg_path: Path, sheet_mm: list[int] | None = None) -> str:
    """Guess strip vs full from template aspect ratio."""
    _, _, vb_w, vb_h = parse_viewbox(svg_path)
    if vb_h <= 0:
        return "strip"
    sheet = sheet_mm or [100, 150]
    aspect = vb_w / vb_h
    strip_aspect = (sheet[0] / 2) / sheet[1]
    full_aspect = sheet[0] / sheet[1]
    if abs(aspect - strip_aspect) <= abs(aspect - full_aspect):
        return "strip"
    return "full"


def _photo_data_url(photo_path: Path, width: int, height: int) -> str:
    with Image.open(photo_path) as img:
        fitted = fit_photo(img, width, height)
        buf = io.BytesIO()
        fitted.save(buf, format="JPEG", quality=92)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def _marker_path_pattern(elem: ET.Element) -> re.Pattern[str]:
    d = elem.get("d", "")
    fill = _parse_fill(elem) or _MARKER_HEX
    return re.compile(
        rf"<path\b(?=[^>]*\bfill=\"{re.escape(fill)}\")"
        rf"(?=[^>]*\bd=\"{re.escape(d)}\")[^>]*/>",
        re.IGNORECASE,
    )


def _make_image_tag(bbox: BBox, href: str) -> str:
    return (
        f'<image x="{bbox.x:.4f}" y="{bbox.y:.4f}" '
        f'width="{bbox.w:.4f}" height="{bbox.h:.4f}" '
        f'preserveAspectRatio="xMidYMid slice" '
        f'xlink:href="{href}"/>'
    )


def compose_svg(
    svg_path: Path,
    photos: list[Path],
    mapping: list[int],
    output: Path,
    *,
    render_width: int | None = None,
    render_height: int | None = None,
) -> Path:
    text = svg_path.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    markers = _find_markers(root)
    if len(markers) != len(mapping):
        raise RuntimeError(f"Expected {len(mapping)} slots, found {len(markers)} green markers")

    _, _, vb_w, vb_h = parse_viewbox_from_root(root)
    px_w = render_width or int(round(vb_w))
    px_h = render_height or int(round(vb_h))
    scale_x = px_w / vb_w if vb_w else 1.0
    scale_y = px_h / vb_h if vb_h else 1.0

    replacements: list[tuple[re.Pattern[str], str]] = []
    for i, (elem, world_bbox, local_bbox) in enumerate(markers):
        photo_idx = mapping[i]
        if photo_idx >= len(photos):
            continue
        img_w = max(1, int(round(world_bbox.w * scale_x)))
        img_h = max(1, int(round(world_bbox.h * scale_y)))
        href = _photo_data_url(photos[photo_idx], img_w, img_h)
        replacements.append((_marker_path_pattern(elem), _make_image_tag(local_bbox, href)))

    for pattern, image_tag in reversed(replacements):
        text, count = pattern.subn(image_tag, text, count=1)
        if count != 1:
            raise RuntimeError("Failed to replace a green marker in the SVG")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def _native_render_size(renderer) -> tuple[int, int]:
    size = renderer.defaultSize()
    if size.width() > 0 and size.height() > 0:
        return size.width(), size.height()
    view_box = renderer.viewBoxF()
    return (
        max(1, int(round(view_box.width()))),
        max(1, int(round(view_box.height()))),
    )


def _qimage_to_pil(image, width: int, height: int) -> Image.Image:
    import numpy as np

    ptr = image.bits()
    ptr.setsize(image.byteCount())
    arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
    rgb = arr[:, :, [2, 1, 0]].copy()
    return Image.fromarray(rgb, "RGB")


def render_svg_to_image(svg_path: Path, width: int, height: int) -> Image.Image:
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QImage, QPainter
    from PyQt5.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG: {svg_path}")

    native_w, native_h = _native_render_size(renderer)
    image = QImage(native_w, native_h, QImage.Format_ARGB32)
    image.fill(Qt.white)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()

    result = _qimage_to_pil(image, native_w, native_h)
    if (native_w, native_h) != (width, height):
        result = result.resize((width, height), Image.Resampling.LANCZOS)
    return result
