from __future__ import annotations

from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QColor, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from photobooth.ui.theme import primary_btn, secondary_btn

_CORNER_STYLE = (
    "font-size: 48px; font-weight: bold; color: white;"
    "background: rgba(0,0,0,160); border-radius: 12px; padding: 12px 20px;"
)
_FINAL_STYLE = (
    "font-size: 96px; font-weight: bold; color: white;"
    "background: transparent; padding: 24px;"
)
_FLASH_STYLE = "background: white;"


def _camera_pixmap(size: int = 96) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("white"), max(3, size // 24))
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    body = size // 8
    top = size // 3
    painter.drawRoundedRect(body, top, size - 2 * body, size - top - body, size // 12, size // 12)
    bump_w = size // 4
    bump_h = size // 10
    painter.drawRoundedRect(
        size // 2 - bump_w // 2, top - bump_h + 2, bump_w, bump_h, 4, 4
    )
    lens = size // 3
    painter.drawEllipse(size // 2 - lens // 2, size // 2 - lens // 6, lens, lens)
    painter.end()
    return pix


class ActionButton(QPushButton):
    """Standard action button used across views."""

    def __init__(
        self,
        text: str,
        parent=None,
        *,
        primary: bool = False,
        height: int = 72,
    ) -> None:
        super().__init__(text, parent)
        self.setMinimumHeight(height)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        if primary:
            self.setStyleSheet(primary_btn(size=24 if height < 64 else 28, radius=12))
        else:
            self.setStyleSheet(secondary_btn(size=18 if height < 64 else 20))


# Backwards compatibility alias
BigButton = ActionButton


class CountdownOverlay(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(0, 0)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet("background: transparent;")
        self.hide()
        self._mode = "corner"

        self._corner_label = QLabel(self)
        self._corner_label.setAlignment(Qt.AlignCenter)

        self._final_panel = QWidget(self)
        final_layout = QVBoxLayout(self._final_panel)
        final_layout.setContentsMargins(24, 24, 24, 24)
        final_layout.setSpacing(16)
        self._camera_icon = QLabel()
        self._camera_icon.setAlignment(Qt.AlignCenter)
        self._camera_icon.setPixmap(_camera_pixmap(96))
        self._message_label = QLabel("Look at the camera")
        self._message_label.setAlignment(Qt.AlignCenter)
        self._message_label.setStyleSheet(
            "font-size: 42px; font-weight: bold; color: white; background: transparent;"
        )
        self._number_label = QLabel()
        self._number_label.setAlignment(Qt.AlignCenter)
        self._number_label.setStyleSheet(
            "font-size: 96px; font-weight: bold; color: white; background: transparent;"
        )
        final_layout.addStretch()
        final_layout.addWidget(self._camera_icon)
        final_layout.addWidget(self._message_label)
        final_layout.addWidget(self._number_label)
        final_layout.addStretch()
        self._final_panel.hide()

    def sizeHint(self) -> QSize:
        return QSize(0, 0)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_layout()

    def _apply_layout(self) -> None:
        if self._mode == "corner":
            margin = 16
            w, h = 100, 80
            self._corner_label.setGeometry(self.width() - w - margin, margin, w, h)
        else:
            self._final_panel.setGeometry(self.rect())

    def show_count(self, n: int) -> None:
        if n > 3:
            self._mode = "corner"
            self.setStyleSheet("background: transparent;")
            self._final_panel.hide()
            self._corner_label.setStyleSheet(_CORNER_STYLE)
            self._corner_label.setText(str(n))
            self._corner_label.show()
        elif n > 0:
            self._mode = "final"
            self.setStyleSheet("background: #111;")
            self._corner_label.hide()
            self._number_label.setText(str(n))
            self._final_panel.show()
        else:
            self._mode = "final"
            self.setStyleSheet("background: #111;")
            self._corner_label.hide()
            self._final_panel.hide()
            self._corner_label.setStyleSheet(_FINAL_STYLE)
            self._corner_label.setText("SMILE!")
            self._corner_label.show()
        self._apply_layout()
        self.show()
        self.raise_()

    def hide_overlay(self) -> None:
        self.hide()
        self.setStyleSheet("background: transparent;")
        self._mode = "corner"
        self._corner_label.hide()
        self._final_panel.hide()

    def flash_white(self) -> None:
        self._mode = "final"
        self.setStyleSheet("background: white;")
        self._final_panel.hide()
        self._corner_label.setText("")
        self._corner_label.setStyleSheet(_FLASH_STYLE)
        self._corner_label.setGeometry(self.rect())
        self._corner_label.show()
        self.show()
        self.raise_()

    def reset_style(self) -> None:
        self.setStyleSheet("background: transparent;")
        self._corner_label.setStyleSheet(_CORNER_STYLE)
        self._corner_label.hide()
        self._final_panel.hide()
        self._mode = "corner"
