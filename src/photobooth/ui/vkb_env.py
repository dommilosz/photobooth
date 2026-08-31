"""Qt Virtual Keyboard environment setup (no PyQt imports)."""

from __future__ import annotations

import os


def enable_qt_virtual_keyboard() -> None:
    """Enable Qt Virtual Keyboard before QApplication is created."""
    os.environ.setdefault("QT_IM_MODULE", "qtvirtualkeyboard")
    # Embedded InputPanel in the settings UI; required for eglfs kiosk mode.
    os.environ.setdefault("QT_VIRTUALKEYBOARD_DESKTOP_DISABLE", "1")
