"""Touch-friendly on-screen keyboard for eglfs / kiosk (no Qt Virtual Keyboard)."""

from __future__ import annotations

from PyQt5.QtCore import QEvent, Qt, pyqtSignal
from PyQt5.QtGui import QKeyEvent
from PyQt5.QtWidgets import (
    QApplication,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from photobooth.ui.theme import (
    ACCENT,
    ACCENT_DIM,
    BG_ELEVATED,
    BG_NAV,
    BORDER,
    FONT_FAMILY,
    TEXT,
)

_ROWS = (
    (list("1234567890"), list("!@#_-+."), list("&?/")),
    (list("qwertyuiop"), list("asdfghjkl"), list("zxcvbnm")),
    (list("QWERTYUIOP"), list("ASDFGHJKL"), list("ZXCVBNM")),
)

_KEY_STYLE = (
    f"QPushButton {{ background: {BG_ELEVATED}; color: {TEXT}; font-family: {FONT_FAMILY};"
    f"font-size: 18px; font-weight: 600; border: 1px solid {BORDER}; border-radius: 8px; }}"
    f"QPushButton:pressed {{ background: {ACCENT}; color: #0a0a0b; border-color: {ACCENT_DIM}; }}"
)
_ACTION_STYLE = (
    f"QPushButton {{ background: #323238; color: {TEXT}; font-family: {FONT_FAMILY};"
    f"font-size: 15px; font-weight: 700; border: 1px solid {BORDER}; border-radius: 8px; }}"
    f"QPushButton:pressed {{ background: {ACCENT}; color: #0a0a0b; border-color: {ACCENT_DIM}; }}"
)
_DONE_STYLE = (
    f"QPushButton {{ background: {ACCENT}; color: #0a0a0b; font-family: {FONT_FAMILY};"
    f"font-size: 15px; font-weight: 700; border: none; border-radius: 8px; }}"
    f"QPushButton:pressed {{ background: {ACCENT_DIM}; }}"
)


class SoftKeyboard(QFrame):
    """QWERTY panel that types into a target QLineEdit via QKeyEvent."""

    dismissed = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode = 1  # 0=symbols, 1=lower, 2=upper
        self._target: QLineEdit | None = None
        self.setObjectName("softKeyboard")
        self.setStyleSheet(
            f"QFrame#softKeyboard {{ background: {BG_NAV}; border-top: 1px solid {BORDER}; }}"
        )
        self.setFocusPolicy(Qt.NoFocus)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(8, 8, 8, 10)
        self._root.setSpacing(6)
        self._grid = QGridLayout()
        self._grid.setSpacing(6)
        self._root.addLayout(self._grid)
        self._rebuild_keys()
        self.hide()

    def _btn(self, label: str, style: str, slot) -> QPushButton:
        btn = QPushButton(label)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(48)
        btn.setStyleSheet(style)
        btn.clicked.connect(slot)
        return btn

    def _rebuild_keys(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()

        rows = _ROWS[self._mode]
        for r, keys in enumerate(rows):
            col0 = max(0, (10 - len(keys)) // 2)
            for c, ch in enumerate(keys):
                self._grid.addWidget(
                    self._btn(ch, _KEY_STYLE, lambda _=False, t=ch: self._type_char(t)),
                    r,
                    col0 + c,
                )

        shift_label = "ABC" if self._mode == 0 else ("⇧" if self._mode == 1 else "⇧✓")
        shift = self._btn(shift_label, _ACTION_STYLE, self._cycle_mode)
        self._grid.addWidget(shift, 2, 0)

        back = self._btn("⌫", _ACTION_STYLE, lambda: self._send_key(Qt.Key_Backspace, ""))
        self._grid.addWidget(back, 2, 11)

        bottom = QWidget()
        bottom.setFocusPolicy(Qt.NoFocus)
        row = QHBoxLayout(bottom)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        mode = self._btn("123" if self._mode != 0 else "abc", _ACTION_STYLE, self._toggle_symbols)
        mode.setFixedWidth(72)
        space = self._btn("space", _KEY_STYLE, lambda: self._send_key(Qt.Key_Space, " "))
        space.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        done = self._btn("Done", _DONE_STYLE, self.hide_keyboard)
        done.setFixedWidth(100)
        row.addWidget(mode)
        row.addWidget(space, stretch=1)
        row.addWidget(done)
        self._grid.addWidget(bottom, 3, 0, 1, 12)

    def _cycle_mode(self) -> None:
        if self._mode == 0:
            self._mode = 1
        elif self._mode == 1:
            self._mode = 2
        else:
            self._mode = 1
        self._rebuild_keys()

    def _toggle_symbols(self) -> None:
        self._mode = 0 if self._mode != 0 else 1
        self._rebuild_keys()

    def _type_char(self, text: str) -> None:
        key = ord(text.upper()) if text.isalpha() else Qt.Key_unknown
        self._send_key(key, text)
        if self._mode == 2:
            self._mode = 1
            self._rebuild_keys()

    def _send_key(self, key: int, text: str) -> None:
        target = self._target
        if target is None:
            return
        target.setFocus(Qt.OtherFocusReason)
        QApplication.sendEvent(target, QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier, text))
        QApplication.sendEvent(target, QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier, text))

    def attach(self, line_edit: QLineEdit) -> None:
        line_edit.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:
        if isinstance(obj, QLineEdit) and event.type() == QEvent.FocusIn:
            self.show_for(obj)
        return super().eventFilter(obj, event)

    def show_for(self, line_edit: QLineEdit) -> None:
        self._target = line_edit
        self._mode = 1
        self._rebuild_keys()
        self.show()
        self.raise_()

    def hide_keyboard(self) -> None:
        was_visible = self.isVisible()
        self.hide()
        self._target = None
        if was_visible:
            self.dismissed.emit()
