from __future__ import annotations

import cv2
import numpy as np
from PyQt5.QtCore import Qt, QSize, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QPainter, QPixmap
from PyQt5.QtWidgets import QSizePolicy, QWidget

from photobooth.ui.theme import BG_DARK


class PreviewViewport(QWidget):
    """Layout cell for camera chrome; ignores child widget size hints."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(0, 0)

    def sizeHint(self) -> QSize:
        return QSize(0, 0)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)


class PreviewWidget(QWidget):
    """Camera preview that scales to fit without affecting parent layout size.

    Tuned for weak devices (Pi Zero): FastTransformation + optional OpenCV
    downscale before converting to QImage.
    """

    frame_ready = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(0, 0)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self._scaled: QPixmap | None = None

    def sizeHint(self) -> QSize:
        return QSize(0, 0)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def show_frame(self, frame: np.ndarray) -> None:
        """Accept BGR uint8 frame (H×W×3) from camera."""
        if frame is None or frame.size == 0:
            return
        tw, th = self.width(), self.height()
        if tw < 1 or th < 1:
            return

        h, w = frame.shape[:2]
        scale = min(tw / w, th / h)
        if abs(scale - 1.0) > 0.02:
            nw = max(1, int(w * scale))
            nh = max(1, int(h * scale))
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
            frame = cv2.resize(frame, (nw, nh), interpolation=interp)
            h, w = frame.shape[:2]

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if not rgb.flags["C_CONTIGUOUS"]:
            rgb = np.ascontiguousarray(rgb)
        qimg = QImage(rgb.data, w, h, rgb.strides[0], QImage.Format_RGB888).copy()
        self._scaled = QPixmap.fromImage(qimg)
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Next frame will re-scale; avoid expensive re-filter here.

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.fillRect(self.rect(), QColor(BG_DARK))
        if self._scaled and not self._scaled.isNull():
            x = (self.width() - self._scaled.width()) // 2
            y = (self.height() - self._scaled.height()) // 2
            painter.drawPixmap(x, y, self._scaled)

    def clear(self) -> None:
        self._scaled = None
        self.update()


class ScaledImageLabel(QWidget):
    """Displays a pixmap scaled to fit without expanding its layout cell."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.setMinimumSize(0, 0)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self._source: QPixmap | None = None
        self._scaled: QPixmap | None = None

    def sizeHint(self) -> QSize:
        return QSize(0, 0)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, 0)

    def set_source_pixmap(self, pixmap: QPixmap | None) -> None:
        self._source = pixmap
        self._rescale()

    def _rescale(self) -> None:
        if not self._source or self.width() < 1 or self.height() < 1:
            self._scaled = None
            self.update()
            return
        self._scaled = self._source.scaled(
            self.size(), Qt.KeepAspectRatio, Qt.FastTransformation
        )
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._rescale()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, False)
        painter.fillRect(self.rect(), QColor(BG_DARK))
        if self._scaled and not self._scaled.isNull():
            x = (self.width() - self._scaled.width()) // 2
            y = (self.height() - self._scaled.height()) // 2
            painter.drawPixmap(x, y, self._scaled)
