from __future__ import annotations

import numpy as np
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from photobooth.compose.template_composer import render_template_preview
from photobooth.compose.template_registry import TemplateRegistry, TemplateSpec
from photobooth.sample_photo import sample_photo_paths
from photobooth.ui.theme import (
    BG_ELEVATED,
    FONT_FAMILY,
    SECTION_TITLE,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    layout_picker_card,
    scroll_horizontal,
)

CARD_W = 280
CARD_H = 340
CARD_BORDER = 3
THUMB_H = 260
THUMB_W = CARD_W - 20
SCROLL_ROW_H = CARD_H + 18


def _pil_to_pixmap(image) -> QPixmap:
    rgb = np.ascontiguousarray(np.array(image.convert("RGB")))
    h, w = rgb.shape[:2]
    qimg = QImage(rgb.data, w, h, w * 3, QImage.Format_RGB888).copy()
    return QPixmap.fromImage(qimg)


def _preview_pixmap(spec: TemplateSpec) -> QPixmap | None:
    if not spec.valid or not spec.slots:
        return None
    mapping = spec.meta.slot_mapping
    if len(spec.slots) != len(mapping):
        return None
    photo_count = max(mapping) + 1 if mapping else spec.capture_count
    photos = sample_photo_paths(photo_count)
    if not photos:
        return None
    tw, th = spec.template_size_px()
    scale = min(THUMB_W / tw, THUMB_H / th)
    render_w, render_h = max(1, int(tw * scale)), max(1, int(th * scale))
    rendered = render_template_preview(spec, photos, width=render_w, height=render_h)
    pix = _pil_to_pixmap(rendered)
    return pix.scaled(render_w, render_h, Qt.KeepAspectRatio, Qt.FastTransformation)


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()
            continue
        child = item.layout()
        if child is not None:
            _clear_layout(child)
            child.deleteLater()


def _horizontal_card_row(cards: list[QWidget]) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setStyleSheet(scroll_horizontal())
    scroll.setFixedHeight(SCROLL_ROW_H)

    container = QWidget()
    row = QHBoxLayout(container)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(16)
    row.setAlignment(Qt.AlignLeft | Qt.AlignTop)
    for card in cards:
        row.addWidget(card)
    row.addStretch()
    scroll.setWidget(container)
    return scroll


class LayoutModeCard(QFrame):
    clicked_mode = pyqtSignal(str)

    def __init__(self, spec, selected: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("layoutModeCard")
        self._mode_id = spec.mode_id
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self._selected = selected
        self._spec = spec
        self._thumb: QLabel | None = None
        self._build()
        self._apply_style()

    def _apply_style(self) -> None:
        self.setStyleSheet(layout_picker_card(self._selected))

    def _build(self) -> None:
        inner_h = CARD_H - 2 * CARD_BORDER
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        thumb_wrap = QFrame()
        thumb_wrap.setStyleSheet(
            f"background: {BG_ELEVATED}; border-radius: 8px; border: none;"
        )
        thumb_layout = QVBoxLayout(thumb_wrap)
        thumb_layout.setContentsMargins(4, 4, 4, 4)
        thumb = QLabel("…")
        thumb.setFixedHeight(min(THUMB_H, inner_h - 64))
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 22px;")
        self._thumb = thumb
        thumb_layout.addWidget(thumb)
        title = QLabel(self._spec.meta.name)
        title.setStyleSheet(
            f"font-family: {FONT_FAMILY}; font-size: 17px; font-weight: 600; color: {TEXT};"
        )
        badge = QLabel(
            f"{self._spec.meta.capture_count} photos · "
            f"{self._spec.meta.sheet_mm[0]}×{self._spec.meta.sheet_mm[1]} mm"
        )
        badge.setStyleSheet(
            f"font-family: {FONT_FAMILY}; font-size: 11px; color: {TEXT_DIM};"
        )
        layout.addWidget(thumb_wrap)
        layout.addWidget(title)
        layout.addWidget(badge)

    def schedule_thumb(self, delay_ms: int = 0) -> None:
        QTimer.singleShot(delay_ms, self._load_thumb)

    def _load_thumb(self) -> None:
        if self._thumb is None:
            return
        preview = _preview_pixmap(self._spec)
        if preview is not None:
            self._thumb.setStyleSheet("")
            self._thumb.setPixmap(preview)
        else:
            self._thumb.setText("⚠" if not self._spec.valid else "?")
            self._thumb.setStyleSheet(f"color: {TEXT_MUTED}; font-size: 28px;")

    def set_selected(self, selected: bool) -> None:
        if self._selected == selected:
            return
        self._selected = selected
        self._apply_style()

    def mousePressEvent(self, event) -> None:
        self.clicked_mode.emit(self._mode_id)
        super().mousePressEvent(event)


class LayoutPickerWidget(QWidget):
    mode_changed = pyqtSignal(str)

    def __init__(self, registry: TemplateRegistry, current: str, parent=None) -> None:
        super().__init__(parent)
        self._registry = registry
        self._current = current
        self._cards: dict[str, LayoutModeCard] = {}
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(12)
        self._build()

    def _section_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(SECTION_TITLE)
        return label

    def _build(self) -> None:
        _clear_layout(self._layout)
        strip_cards: list[LayoutModeCard] = []
        full_cards: list[LayoutModeCard] = []
        for i, spec in enumerate(self._registry.list_modes()):
            card = LayoutModeCard(spec, selected=spec.mode_id == self._current)
            card.clicked_mode.connect(self._on_click)
            card.schedule_thumb(i * 50)
            self._cards[spec.mode_id] = card
            if spec.meta.category == "strip":
                strip_cards.append(card)
            else:
                full_cards.append(card)

        self._layout.addWidget(self._section_label("Strip modes · 10×15 cm"))
        if strip_cards:
            self._layout.addWidget(_horizontal_card_row(strip_cards))

        self._layout.addSpacing(4)
        self._layout.addWidget(self._section_label("Full sheet · 10×15 cm"))
        if full_cards:
            full_grid = QGridLayout()
            full_grid.setSpacing(16)
            full_grid.setAlignment(Qt.AlignLeft | Qt.AlignTop)
            for i, card in enumerate(full_cards):
                full_grid.addWidget(card, i // 2, i % 2, Qt.AlignLeft | Qt.AlignTop)
            self._layout.addLayout(full_grid)

    def _on_click(self, mode_id: str) -> None:
        self.set_mode(mode_id)
        self.mode_changed.emit(mode_id)

    def current_mode(self) -> str:
        return self._current

    def set_mode(self, mode_id: str) -> None:
        if self._current == mode_id:
            return
        self._current = mode_id
        for mid, card in self._cards.items():
            card.set_selected(mid == mode_id)

    def reload(self) -> None:
        self._cards.clear()
        self._registry.rescan()
        self._build()
