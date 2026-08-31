from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWidgets import QSizePolicy, QWidget

log = logging.getLogger(__name__)

_QML = Path(__file__).with_name("input_panel.qml")


def create_virtual_keyboard_panel(parent: QWidget | None = None) -> QWidget | None:
    """Return an embedded Qt Virtual Keyboard panel, or None if unavailable."""
    try:
        from PyQt5.QtQuickWidgets import QQuickWidget
    except ImportError:
        log.warning("PyQt5.QtQuickWidgets not installed; virtual keyboard disabled")
        return None

    if not _QML.is_file():
        log.warning("Missing %s; virtual keyboard disabled", _QML)
        return None

    quick = QQuickWidget(parent)
    quick.setResizeMode(QQuickWidget.SizeViewToRootObject)
    quick.setClearColor(Qt.transparent)
    quick.setSource(QUrl.fromLocalFile(str(_QML.resolve())))
    if quick.status() == QQuickWidget.Error:
        log.warning("Virtual keyboard QML failed to load: %s", quick.errors())
        quick.deleteLater()
        return None

    quick.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    quick.setFocusPolicy(Qt.NoFocus)
    return quick
