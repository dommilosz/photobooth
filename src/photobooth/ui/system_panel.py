"""System settings panel: network info, Wi-Fi, reboot / shutdown."""

from __future__ import annotations

import logging

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from photobooth import system_ctl
from photobooth.ui.soft_keyboard import SoftKeyboard
from photobooth.ui.theme import (
    BG_PAGE,
    FIELD_LABEL,
    FONT_FAMILY,
    LINE_EDIT,
    PAGE_TITLE,
    SCROLL_AREA,
    SECTION_TITLE,
    TEXT,
    TEXT_MUTED,
    card_style,
    danger_btn,
    nav_bar,
    primary_btn,
    secondary_btn,
)
from photobooth.ui.widgets import ActionButton, enable_touch_scroll

log = logging.getLogger(__name__)

_STATUS_VALUE = (
    f"color: {TEXT}; font-family: {FONT_FAMILY}; font-size: 16px; font-weight: 600;"
    "background: transparent;"
)
_STATUS_HINT = (
    f"color: {TEXT_MUTED}; font-family: {FONT_FAMILY}; font-size: 13px;"
    "background: transparent;"
)
_WIFI_ROW = (
    f"QPushButton {{ background: #28282c; color: {TEXT}; font-family: {FONT_FAMILY};"
    "font-size: 15px; font-weight: 600; text-align: left; padding: 14px 16px;"
    "border: 1px solid #34343a; border-radius: 10px; }"
    "QPushButton:hover { background: #323238; }"
    "QPushButton:pressed { background: #222226; }"
    "QPushButton:checked { border-color: #3ecf8e; background: rgba(62, 207, 142, 0.14); }"
)


class _WifiScanWorker(QThread):
    finished_ok = pyqtSignal(list)
    failed = pyqtSignal(str)

    def run(self) -> None:
        try:
            self.finished_ok.emit(system_ctl.scan_wifi())
        except Exception as exc:
            self.failed.emit(str(exc))


class _WifiConnectWorker(QThread):
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, ssid: str, password: str) -> None:
        super().__init__()
        self._ssid = ssid
        self._password = password

    def run(self) -> None:
        try:
            system_ctl.connect_wifi(self._ssid, self._password)
            self.finished_ok.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class SystemPanel(QWidget):
    back_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG_PAGE};")
        self._selected_ssid = ""
        self._scan_worker: _WifiScanWorker | None = None
        self._connect_worker: _WifiConnectWorker | None = None
        self._network_btns: list[QPushButton] = []
        self._soft_keyboard: SoftKeyboard | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_nav())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(SCROLL_AREA)
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 32)
        layout.setSpacing(16)

        layout.addWidget(self._section("Network"))
        net_card = self._card()
        net_layout = QVBoxLayout(net_card)
        net_layout.setContentsMargins(16, 14, 16, 14)
        net_layout.setSpacing(10)

        self._hostname_label = QLabel("—")
        self._hostname_label.setStyleSheet(_STATUS_VALUE)
        self._ip_label = QLabel("—")
        self._ip_label.setWordWrap(True)
        self._ip_label.setStyleSheet(_STATUS_VALUE)
        self._wifi_label = QLabel("—")
        self._wifi_label.setWordWrap(True)
        self._wifi_label.setStyleSheet(_STATUS_VALUE)
        self._net_hint = QLabel("")
        self._net_hint.setWordWrap(True)
        self._net_hint.setStyleSheet(_STATUS_HINT)

        net_layout.addWidget(self._field_label("Hostname"))
        net_layout.addWidget(self._hostname_label)
        net_layout.addWidget(self._field_label("IP address"))
        net_layout.addWidget(self._ip_label)
        net_layout.addWidget(self._field_label("Wi-Fi"))
        net_layout.addWidget(self._wifi_label)
        net_layout.addWidget(self._net_hint)
        refresh = ActionButton("Refresh status", height=52)
        refresh.clicked.connect(self.refresh_status)
        net_layout.addWidget(refresh)
        layout.addWidget(net_card)

        layout.addWidget(self._section("Wi-Fi networks"))
        wifi_card = self._card()
        wifi_layout = QVBoxLayout(wifi_card)
        wifi_layout.setContentsMargins(16, 14, 16, 14)
        wifi_layout.setSpacing(10)

        self._wifi_status = QLabel("Scan to list nearby networks.")
        self._wifi_status.setWordWrap(True)
        self._wifi_status.setStyleSheet(_STATUS_HINT)
        wifi_layout.addWidget(self._wifi_status)

        self._networks_box = QVBoxLayout()
        self._networks_box.setSpacing(8)
        wifi_layout.addLayout(self._networks_box)

        self._password_label = QLabel("Password")
        self._password_label.setStyleSheet(FIELD_LABEL)
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.Password)
        self._password_edit.setPlaceholderText("Leave empty if open network")
        self._password_edit.setStyleSheet(LINE_EDIT)
        self._password_label.hide()
        self._password_edit.hide()
        wifi_layout.addWidget(self._password_label)
        wifi_layout.addWidget(self._password_edit)

        row = QHBoxLayout()
        row.setSpacing(10)
        self._scan_btn = ActionButton("Scan", height=52)
        self._scan_btn.clicked.connect(self._start_scan)
        self._connect_btn = ActionButton("Connect", height=52, primary=True)
        self._connect_btn.clicked.connect(self._start_connect)
        self._connect_btn.setEnabled(False)
        row.addWidget(self._scan_btn, stretch=1)
        row.addWidget(self._connect_btn, stretch=1)
        wifi_layout.addLayout(row)
        layout.addWidget(wifi_card)

        layout.addWidget(self._section("Power"))
        power_card = self._card()
        power_layout = QVBoxLayout(power_card)
        power_layout.setContentsMargins(12, 12, 12, 12)
        power_layout.setSpacing(8)
        exit_btn = ActionButton("Exit to terminal", height=56)
        exit_btn.clicked.connect(self._confirm_exit)
        reboot_btn = QPushButton("Reboot")
        reboot_btn.setMinimumHeight(56)
        reboot_btn.setCursor(Qt.PointingHandCursor)
        reboot_btn.setStyleSheet(danger_btn(size=18, radius=12, pad="0 20px"))
        reboot_btn.clicked.connect(lambda: self._confirm_power("reboot"))
        shutdown_btn = QPushButton("Shut down")
        shutdown_btn.setMinimumHeight(56)
        shutdown_btn.setCursor(Qt.PointingHandCursor)
        shutdown_btn.setStyleSheet(danger_btn(size=18, radius=12, pad="0 20px"))
        shutdown_btn.clicked.connect(lambda: self._confirm_power("shutdown"))
        power_layout.addWidget(exit_btn)
        power_layout.addWidget(reboot_btn)
        power_layout.addWidget(shutdown_btn)
        layout.addWidget(power_card)

        layout.addStretch()
        scroll.setWidget(content)
        enable_touch_scroll(scroll)
        root.addWidget(scroll, stretch=1)

    def _build_nav(self) -> QFrame:
        nav = QFrame()
        nav.setFixedHeight(72)
        nav.setStyleSheet(nav_bar())
        row = QHBoxLayout(nav)
        row.setContentsMargins(16, 8, 16, 8)
        back = QPushButton("Back")
        back.setFixedSize(100, 48)
        back.setCursor(Qt.PointingHandCursor)
        back.setStyleSheet(secondary_btn(size=15, radius=10, pad="0 16px"))
        back.clicked.connect(self.back_requested.emit)
        title = QLabel("System")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(PAGE_TITLE)
        spacer = QWidget()
        spacer.setFixedSize(100, 48)
        row.addWidget(back)
        row.addWidget(title, stretch=1)
        row.addWidget(spacer)
        return nav

    def _section(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setStyleSheet(SECTION_TITLE)
        return label

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet(FIELD_LABEL)
        return label

    def _card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(card_style())
        return card

    def attach_keyboard(self, keyboard: SoftKeyboard | None) -> None:
        self._soft_keyboard = keyboard
        if keyboard is not None:
            keyboard.attach(self._password_edit)

    def refresh_status(self) -> None:
        status = system_ctl.network_status()
        self._hostname_label.setText(status.hostname)
        if status.ipv4:
            self._ip_label.setText("\n".join(status.ipv4))
        else:
            self._ip_label.setText("No IPv4 address")
        if status.wifi_ssid:
            self._wifi_label.setText(f"Connected · {status.wifi_ssid}")
        elif status.wifi_available:
            self._wifi_label.setText("Not connected")
        else:
            self._wifi_label.setText("Unavailable")
        self._net_hint.setText(status.detail)
        self._scan_btn.setEnabled(status.wifi_available)
        if not status.wifi_available:
            self._connect_btn.setEnabled(False)

    def _clear_networks(self) -> None:
        while self._networks_box.count():
            item = self._networks_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._network_btns.clear()

    def _start_scan(self) -> None:
        if self._scan_worker is not None and self._scan_worker.isRunning():
            return
        self._wifi_status.setText("Scanning...")
        self._scan_btn.setEnabled(False)
        self._clear_networks()
        worker = _WifiScanWorker()
        self._scan_worker = worker
        worker.finished_ok.connect(self._on_scan_ok)
        worker.failed.connect(self._on_scan_fail)
        worker.finished.connect(lambda: self._scan_btn.setEnabled(True))
        worker.start()

    def _on_scan_ok(self, networks: list) -> None:
        self._clear_networks()
        if not networks:
            self._wifi_status.setText("No networks found.")
            return
        self._wifi_status.setText(f"{len(networks)} networks — tap one to connect.")
        for net in networks:
            label = net.ssid
            meta = f"{net.signal}%"
            if net.security and net.security not in ("--", ""):
                meta += f" · {net.security}"
            if net.active:
                meta += " · connected"
            btn = QPushButton(f"{label}\n{meta}")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(_WIFI_ROW)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _=False, s=net.ssid, b=btn: self._select_ssid(s, b))
            self._networks_box.addWidget(btn)
            self._network_btns.append(btn)
            if net.active:
                self._select_ssid(net.ssid, btn)

    def _on_scan_fail(self, message: str) -> None:
        self._wifi_status.setText(f"Scan failed: {message}")
        log.warning("Wi-Fi scan failed: %s", message)

    def _select_ssid(self, ssid: str, button: QPushButton) -> None:
        self._selected_ssid = ssid
        for btn in self._network_btns:
            btn.setChecked(btn is button)
        self._password_label.show()
        self._password_edit.show()
        self._password_edit.clear()
        self._connect_btn.setEnabled(True)
        self._wifi_status.setText(f"Selected: {ssid}")

    def _start_connect(self) -> None:
        if not self._selected_ssid:
            return
        if self._connect_worker is not None and self._connect_worker.isRunning():
            return
        password = self._password_edit.text()
        self._wifi_status.setText(f"Connecting to {self._selected_ssid}...")
        self._connect_btn.setEnabled(False)
        self._scan_btn.setEnabled(False)
        worker = _WifiConnectWorker(self._selected_ssid, password)
        self._connect_worker = worker
        worker.finished_ok.connect(self._on_connect_ok)
        worker.failed.connect(self._on_connect_fail)
        worker.finished.connect(self._on_connect_finished)
        worker.start()

    def _on_connect_ok(self) -> None:
        self._wifi_status.setText(f"Connected to {self._selected_ssid}.")
        self.refresh_status()

    def _on_connect_fail(self, message: str) -> None:
        self._wifi_status.setText(f"Connect failed: {message}")
        log.warning("Wi-Fi connect failed: %s", message)

    def _on_connect_finished(self) -> None:
        self._connect_btn.setEnabled(bool(self._selected_ssid))
        self._scan_btn.setEnabled(True)

    def _confirm_exit(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle("Exit")
        box.setText("Close the photobooth GUI and return to the terminal?")
        box.setIcon(QMessageBox.Question)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.setStyleSheet(
            f"QLabel {{ color: {TEXT}; font-size: 15px; min-width: 280px; }}"
            f"QPushButton {{ min-width: 88px; min-height: 40px; font-size: 14px; }}"
        )
        if box.exec_() == QMessageBox.Yes:
            self.exit_requested.emit()

    def _confirm_power(self, action: str) -> None:
        if action == "reboot":
            title = "Reboot"
            body = "Restart this Raspberry Pi now?"
        else:
            title = "Shut down"
            body = "Power off this Raspberry Pi now?"

        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(body)
        box.setIcon(QMessageBox.Warning)
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        box.setStyleSheet(
            f"QLabel {{ color: {TEXT}; font-size: 15px; min-width: 280px; }}"
            f"QPushButton {{ min-width: 88px; min-height: 40px; font-size: 14px; }}"
        )
        if box.exec_() != QMessageBox.Yes:
            return
        try:
            if action == "reboot":
                system_ctl.reboot()
                self._wifi_status.setText("Rebooting...")
            else:
                system_ctl.shutdown()
                self._wifi_status.setText("Shutting down...")
        except Exception as exc:
            log.exception("%s failed", action)
            err = QMessageBox(self)
            err.setWindowTitle(title)
            err.setIcon(QMessageBox.Critical)
            err.setText(str(exc))
            err.setStyleSheet(
                f"QLabel {{ color: {TEXT}; font-size: 14px; min-width: 280px; }}"
            )
            err.exec_()
