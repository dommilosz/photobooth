from __future__ import annotations

import logging
from pathlib import Path

from PyQt5.QtCore import QThread, QTimer, Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from photobooth.backends.camera import CameraBackend
from photobooth.backends.flash import FlashBackend
from photobooth.backends.printer import PrinterBackend
from photobooth.backends.upload import UploadBackend
from photobooth.compose.template_composer import compose_sheet
from photobooth.compose.template_registry import TemplateRegistry
from photobooth.config import save_config
from photobooth.paths import app_root
from photobooth.session import CaptureSession, SessionWorker, make_session_id
from photobooth.ui.layout_picker import LayoutPickerWidget
from photobooth.ui.preview import PreviewViewport, PreviewWidget, ScaledImageLabel
from photobooth.ui.theme import (
    BG_DARK,
    BG_PAGE,
    CHECKBOX,
    FIELD_LABEL,
    FONT_FAMILY,
    LAYOUT_PILL,
    LINE_EDIT,
    LINK_BTN,
    PAGE_TITLE,
    SCROLL_AREA,
    SECTION_TITLE,
    SPINBOX,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    card_style,
    dock_bar,
    nav_bar,
    primary_btn,
    secondary_btn,
)
from photobooth.ui.widgets import ActionButton, CountdownOverlay

log = logging.getLogger(__name__)


class UploadWorker(QThread):
    finished_ok = pyqtSignal(bool)

    def __init__(self, upload: UploadBackend, session_id: str, files: dict[str, Path]) -> None:
        super().__init__()
        self._upload = upload
        self._session_id = session_id
        self._files = files

    def run(self) -> None:
        ok = self._upload.upload_session(self._session_id, self._files)
        self.finished_ok.emit(ok)


class PhotoboothApp(QWidget):
    def __init__(
        self,
        cfg: dict,
        camera: CameraBackend,
        flash: FlashBackend,
        printer: PrinterBackend,
        upload: UploadBackend,
        registry: TemplateRegistry,
    ) -> None:
        super().__init__()
        self.cfg = cfg
        self.camera = camera
        self.flash = flash
        self.printer = printer
        self.upload = upload
        self.registry = registry
        self._session_paths: list[str] = []
        self._sheet_path: Path | None = None
        self._session_id = ""
        self._worker: SessionWorker | None = None
        self._suppress_preview = False
        self._progress = QLabel()
        self._progress.setAlignment(Qt.AlignCenter)

        self._preview_host = QWidget()
        self._preview_host.setStyleSheet(f"background: {BG_DARK};")

        self._top_bar = self._build_top_bar()
        self._top_bar.setFixedHeight(64)

        self._preview_viewport = PreviewViewport()
        self._preview = PreviewWidget(self._preview_viewport)
        self._countdown = CountdownOverlay(self._preview_viewport)
        self._preview_viewport.installEventFilter(self)

        self._bottom_idle = self._build_bottom_idle()
        self._bottom_idle.setFixedHeight(132)
        self._bottom_capture = self._build_bottom_capture()
        self._bottom_capture.setFixedHeight(72)
        self._bottom_stack = QStackedWidget()
        self._bottom_stack.addWidget(self._bottom_idle)
        self._bottom_stack.addWidget(self._bottom_capture)

        host_layout = QVBoxLayout(self._preview_host)
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(0)
        host_layout.addWidget(self._top_bar)
        host_layout.addWidget(self._preview_viewport, stretch=1)
        host_layout.addWidget(self._bottom_stack)

        self._review_image = ScaledImageLabel()
        self._review_source: QPixmap | None = None
        self._upload_status = QLabel("")
        self._upload_status.setAlignment(Qt.AlignCenter)

        self._build_ui()
        self._show_idle()
        self.camera.set_frame_callback(self._on_frame)
        self.camera.start_preview()
        self._mock_timer = QTimer(self)
        self._mock_timer.timeout.connect(self._pump_mock)
        if hasattr(self.camera, "pump_frame"):
            self._mock_timer.start(33)
        self._retry_timer = QTimer(self)
        self._retry_timer.timeout.connect(self.upload.retry_pending)
        self._retry_timer.start(int(cfg.get("upload", {}).get("retry_interval_sec", 300)) * 1000)
        self.upload.retry_pending()

    def _sync_preview_chrome(self) -> None:
        w, h = self._preview_viewport.width(), self._preview_viewport.height()
        if w < 1 or h < 1:
            return
        self._preview.setGeometry(0, 0, w, h)
        self._countdown.setGeometry(0, 0, w, h)
        self._countdown.raise_()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._preview_viewport and event.type() == QEvent.Resize:
            self._sync_preview_chrome()
        return super().eventFilter(obj, event)

    def _pump_mock(self) -> None:
        if hasattr(self.camera, "pump_frame"):
            self.camera.pump_frame()

    def _on_frame(self, frame) -> None:
        if self._main_stack.currentIndex() == 0 and not self._suppress_preview:
            self._preview.show_frame(frame)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._main_stack = QStackedWidget()
        root.addWidget(self._main_stack)

        camera_page = QWidget()
        cam_layout = QVBoxLayout(camera_page)
        cam_layout.setContentsMargins(0, 0, 0, 0)
        cam_layout.addWidget(self._preview_host, stretch=1)
        self._main_stack.addWidget(camera_page)
        self._main_stack.addWidget(self._build_review_page())
        self._main_stack.addWidget(self._build_settings())

    def _make_page_nav(self, title_text: str) -> QFrame:
        nav = QFrame()
        nav.setFixedHeight(72)
        nav.setStyleSheet(nav_bar())
        row = QHBoxLayout(nav)
        row.setContentsMargins(20, 8, 20, 8)
        title = QLabel(title_text)
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(PAGE_TITLE)
        row.addWidget(title)
        return nav

    def _make_bottom_dock(self) -> QFrame:
        dock = QFrame()
        dock.setFixedHeight(100)
        dock.setStyleSheet(dock_bar())
        return dock

    def _build_review_page(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background: {BG_PAGE};")
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._make_page_nav("Review & Print"))

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 16)
        content_layout.setSpacing(16)

        frame = QFrame()
        frame.setStyleSheet(card_style())
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(16, 16, 16, 16)
        frame_layout.addWidget(self._review_image)
        content_layout.addWidget(frame, stretch=1)

        self._upload_status.setStyleSheet(
            f"color: {TEXT_DIM}; font-family: {FONT_FAMILY}; font-size: 14px;"
            "background: transparent; padding: 6px;"
        )
        content_layout.addWidget(self._upload_status)
        root.addWidget(content, stretch=1)

        dock = self._make_bottom_dock()
        dock_row = QHBoxLayout(dock)
        dock_row.setContentsMargins(20, 16, 20, 16)
        dock_row.setSpacing(16)
        retake = ActionButton("Retake")
        retake.clicked.connect(self._show_idle)
        print_btn = ActionButton("Print", primary=True)
        print_btn.clicked.connect(self._do_print)
        dock_row.addWidget(retake, stretch=1)
        dock_row.addWidget(print_btn, stretch=2)
        root.addWidget(dock)
        return page

    def _update_layout_badge(self) -> None:
        mode = self.cfg.get("layout", {}).get("mode", "strip_4_classic")
        spec = self.registry.load(mode)
        self._layout_badge.setText(spec.meta.name)
        self._layout_detail.setText(
            f"{spec.capture_count} photos · "
            f"{spec.meta.sheet_mm[0]}×{spec.meta.sheet_mm[1]} mm"
        )

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(nav_bar())
        row = QHBoxLayout(bar)
        row.setContentsMargins(20, 12, 20, 12)
        self._event_label = QLabel(self.cfg.get("event_name", "photobooth"))
        self._event_label.setStyleSheet(
            f"color: {TEXT}; font-family: {FONT_FAMILY}; font-size: 17px;"
            "font-weight: 600; background: transparent; letter-spacing: 0.3px;"
        )
        settings_btn = QPushButton("Settings")
        settings_btn.setFixedHeight(40)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setStyleSheet(secondary_btn(size=14, radius=10, pad="0 16px"))
        settings_btn.clicked.connect(self._show_settings)
        row.addWidget(self._event_label)
        row.addStretch()
        row.addWidget(settings_btn)
        return bar

    def _build_bottom_idle(self) -> QFrame:
        dock = QFrame()
        dock.setStyleSheet(dock_bar())
        row = QHBoxLayout(dock)
        row.setContentsMargins(20, 16, 20, 20)
        row.setSpacing(16)

        layout_btn = QFrame()
        layout_btn.setCursor(Qt.PointingHandCursor)
        layout_btn.setStyleSheet(LAYOUT_PILL)
        layout_inner = QVBoxLayout(layout_btn)
        layout_inner.setContentsMargins(16, 12, 16, 12)
        layout_inner.setSpacing(3)
        self._layout_badge = QLabel()
        self._layout_badge.setStyleSheet(
            f"color: {TEXT}; font-family: {FONT_FAMILY}; font-size: 15px;"
            "font-weight: 600; background: transparent;"
        )
        self._layout_detail = QLabel()
        self._layout_detail.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: {FONT_FAMILY}; font-size: 12px;"
            "background: transparent;"
        )
        layout_inner.addWidget(self._layout_badge)
        layout_inner.addWidget(self._layout_detail)
        layout_btn.mousePressEvent = lambda _e: self._show_settings()  # type: ignore

        start = QPushButton("START")
        start.setCursor(Qt.PointingHandCursor)
        start.setMinimumHeight(72)
        start.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        start.setStyleSheet(primary_btn())
        start.clicked.connect(self._start_capture)

        row.addWidget(layout_btn, stretch=2)
        row.addWidget(start, stretch=3)
        self._update_layout_badge()
        return dock

    def _build_bottom_capture(self) -> QFrame:
        bar = QFrame()
        bar.setStyleSheet(
            f"QFrame {{ background: rgba(10, 10, 11, 0.92); border-top: 1px solid #2a2a2e; }}"
        )
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(24, 12, 24, 14)
        layout.setSpacing(4)
        self._progress.setStyleSheet(
            f"font-family: {FONT_FAMILY}; font-size: 20px; color: {TEXT};"
            "background: transparent; font-weight: 600;"
        )
        self._capture_hint = QLabel("Smile when the countdown ends")
        self._capture_hint.setAlignment(Qt.AlignCenter)
        self._capture_hint.setStyleSheet(
            f"color: {TEXT_MUTED}; font-family: {FONT_FAMILY}; font-size: 13px;"
            "background: transparent;"
        )
        layout.addWidget(self._progress)
        layout.addWidget(self._capture_hint)
        return bar

    def _build_settings(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet(f"background: {BG_PAGE};")
        root = QVBoxLayout(page)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        nav = QFrame()
        nav.setFixedHeight(72)
        nav.setStyleSheet(nav_bar())
        nav_row = QHBoxLayout(nav)
        nav_row.setContentsMargins(16, 8, 16, 8)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 48)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(secondary_btn(size=15, radius=10, pad="0 16px"))
        cancel_btn.clicked.connect(self._cancel_settings)
        title = QLabel("Settings")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(PAGE_TITLE)
        save_btn = QPushButton("Save")
        save_btn.setFixedSize(100, 48)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(primary_btn(size=15, radius=10, pad="0 20px"))
        save_btn.clicked.connect(self._save_and_exit_settings)
        nav_row.addWidget(cancel_btn)
        nav_row.addWidget(title, stretch=1)
        nav_row.addWidget(save_btn)
        root.addWidget(nav)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet(SCROLL_AREA)
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 20, 20, 32)
        layout.setSpacing(16)

        layout.addWidget(self._settings_section_title("Print layout"))
        layout_card = self._settings_card()
        layout_card_layout = QVBoxLayout(layout_card)
        layout_card_layout.setContentsMargins(16, 16, 16, 16)
        layout_card_layout.setSpacing(12)
        picker = LayoutPickerWidget(
            self.registry, self.cfg.get("layout", {}).get("mode", "strip_4_classic")
        )
        self._picker = picker
        layout_card_layout.addWidget(picker)
        reload_btn = QPushButton("Reload templates from disk")
        reload_btn.setCursor(Qt.PointingHandCursor)
        reload_btn.setStyleSheet(LINK_BTN)
        reload_btn.clicked.connect(self._reload_templates)
        layout_card_layout.addWidget(reload_btn)
        layout.addWidget(layout_card)

        layout.addWidget(self._settings_section_title("Capture"))
        capture_card = self._settings_card()
        capture_layout = QVBoxLayout(capture_card)
        capture_layout.setContentsMargins(16, 14, 16, 14)
        capture_layout.setSpacing(10)
        countdown_label = QLabel("Countdown (seconds)")
        countdown_label.setStyleSheet(FIELD_LABEL)
        self._countdown_spin = QSpinBox()
        self._countdown_spin.setRange(1, 15)
        self._countdown_spin.setValue(int(self.cfg.get("capture", {}).get("countdown_seconds", 3)))
        self._countdown_spin.setStyleSheet(SPINBOX)
        capture_layout.addWidget(countdown_label)
        capture_layout.addWidget(self._countdown_spin)
        layout.addWidget(capture_card)

        layout.addWidget(self._settings_section_title("Event"))
        event_card = self._settings_card()
        event_layout = QVBoxLayout(event_card)
        event_layout.setContentsMargins(16, 14, 16, 14)
        event_label = QLabel("Event name")
        event_label.setStyleSheet(FIELD_LABEL)
        self._event_edit = QLineEdit(self.cfg.get("event_name", "photobooth"))
        self._event_edit.setStyleSheet(LINE_EDIT)
        event_layout.addWidget(event_label)
        event_layout.addWidget(self._event_edit)
        layout.addWidget(event_card)

        layout.addWidget(self._settings_section_title("Display"))
        display_card = self._settings_card()
        display_layout = QVBoxLayout(display_card)
        display_layout.setContentsMargins(16, 14, 16, 14)
        self._fullscreen_check = QCheckBox("Fullscreen")
        self._fullscreen_check.setStyleSheet(CHECKBOX)
        self._fullscreen_check.setCursor(Qt.PointingHandCursor)
        display_layout.addWidget(self._fullscreen_check)
        layout.addWidget(display_card)

        layout.addWidget(self._settings_section_title("Diagnostics"))
        diag_card = self._settings_card()
        diag_layout = QVBoxLayout(diag_card)
        diag_layout.setContentsMargins(12, 12, 12, 12)
        diag_layout.setSpacing(8)
        test_flash = ActionButton("Test flash (1s)", height=56)
        test_flash.clicked.connect(lambda: self.flash.test_pulse(1000))
        test_upload = ActionButton("Test Nextcloud upload", height=56)
        test_upload.clicked.connect(lambda: self.upload.test_connection())
        diag_layout.addWidget(test_flash)
        diag_layout.addWidget(test_upload)
        layout.addWidget(diag_card)

        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)
        return page

    def _settings_section_title(self, text: str) -> QLabel:
        label = QLabel(text.upper())
        label.setStyleSheet(SECTION_TITLE)
        return label

    def _settings_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(card_style())
        return card

    def _cancel_settings(self) -> None:
        self._show_idle()

    def _save_and_exit_settings(self) -> None:
        self._save_settings()
        self._show_idle()

    def _load_settings_form(self) -> None:
        self._countdown_spin.setValue(int(self.cfg.get("capture", {}).get("countdown_seconds", 3)))
        self._event_edit.setText(self.cfg.get("event_name", "photobooth"))
        self._picker.set_mode(self.cfg.get("layout", {}).get("mode", "strip_4_classic"))
        self._fullscreen_check.setChecked(self.cfg.get("display", {}).get("fullscreen", False))

    def _save_settings(self) -> None:
        self.cfg.setdefault("capture", {})["countdown_seconds"] = self._countdown_spin.value()
        self.cfg["event_name"] = self._event_edit.text().strip() or "photobooth"
        self.cfg.setdefault("layout", {})["mode"] = self._picker.current_mode()
        self.cfg.setdefault("display", {})["fullscreen"] = self._fullscreen_check.isChecked()
        save_config(self.cfg)
        self._update_layout_badge()
        self._event_label.setText(self.cfg["event_name"])
        self.apply_display_mode()

    def _reload_templates(self) -> None:
        self._picker.reload()

    def _show_idle(self) -> None:
        self._main_stack.setCurrentIndex(0)
        self._bottom_stack.setCurrentIndex(0)
        self._bottom_stack.show()
        self._top_bar.show()
        self._suppress_preview = False
        self._countdown.hide_overlay()
        self._countdown.reset_style()
        self._update_layout_badge()
        self._event_label.setText(self.cfg.get("event_name", "photobooth"))
        self._sync_preview_chrome()

    def _show_settings(self) -> None:
        self._load_settings_form()
        self._main_stack.setCurrentIndex(2)

    def _start_capture(self) -> None:
        mode = self.cfg.get("layout", {}).get("mode", "strip_4_classic")
        n = self.registry.photo_count(mode)
        self._progress.setText(f"Photo 0 of {n}")
        self._main_stack.setCurrentIndex(0)
        self._bottom_stack.setCurrentIndex(1)
        self._bottom_stack.show()
        self._sync_preview_chrome()
        self._session_id = make_session_id(self.cfg.get("event_name", "photobooth"))
        sessions = app_root() / self.cfg.get("paths", {}).get("sessions_dir", "data/sessions")
        session_dir = sessions / self._session_id
        flash_cfg = self.cfg.get("flash", {})
        cap = self.cfg.get("capture", {})
        session = CaptureSession(
            self.camera,
            self.flash,
            session_dir,
            n,
            int(cap.get("countdown_seconds", 3)),
            int(cap.get("inter_photo_pause_ms", 500)),
            int(flash_cfg.get("warmup_ms", 80)),
            int(flash_cfg.get("duration_ms", 200)),
        )
        session.countdown_tick.connect(self._on_countdown)
        session.photo_taken.connect(self._on_photo_taken)
        session.session_complete.connect(self._on_session_complete)
        session.error.connect(self._on_error)
        self._worker = SessionWorker(session)
        self._worker.start()

    def _on_countdown(self, n: int) -> None:
        self._suppress_preview = n <= 3
        if self._suppress_preview:
            self._preview.clear()
            self._top_bar.hide()
            self._bottom_stack.hide()
        else:
            self._top_bar.show()
            if self._main_stack.currentIndex() == 0:
                self._bottom_stack.show()
        self._countdown.show_count(n)
        self._countdown.raise_()
        if n == 0:
            self._countdown.flash_white()
            QTimer.singleShot(150, self._countdown.reset_style)

    def _on_photo_taken(self, num: int, path: str) -> None:
        self._suppress_preview = False
        self._top_bar.show()
        self._bottom_stack.show()
        mode = self.cfg.get("layout", {}).get("mode", "strip_4_classic")
        total = self.registry.photo_count(mode)
        self._progress.setText(f"Photo {num} of {total}")

    def _on_session_complete(self, paths: list) -> None:
        self._session_paths = paths
        self._suppress_preview = False
        self._countdown.hide_overlay()
        mode = self.cfg.get("layout", {}).get("mode", "strip_4_classic")
        prints = app_root() / self.cfg.get("paths", {}).get("prints_dir", "data/prints")
        self._sheet_path = prints / f"{self._session_id}_sheet.jpg"
        try:
            compose_sheet([Path(p) for p in paths], self.registry, mode, self._sheet_path)
        except Exception as e:
            log.exception("Compose failed")
            self._on_error(str(e))
            return
        self._review_source = QPixmap(str(self._sheet_path))
        self._update_review_image()
        self._main_stack.setCurrentIndex(1)
        self._upload_status.setText("Uploading…")
        files = {Path(p).name: Path(p) for p in paths}
        files["sheet.jpg"] = self._sheet_path
        self._upload_worker = UploadWorker(self.upload, self._session_id, files)
        self._upload_worker.finished_ok.connect(self._on_upload_done)
        self._upload_worker.start()

    def _on_upload_done(self, ok: bool) -> None:
        icon = "☁" if ok else "⚠"
        msg = "Uploaded to cloud" if ok else "Upload failed — queued for retry"
        self._upload_status.setText(f"{icon}  {msg}")

    def _do_print(self) -> None:
        if not self._sheet_path:
            return
        spec = self.registry.load(self.cfg.get("layout", {}).get("mode", "strip_4_classic"))
        self.printer.print_image(self._sheet_path, spec.meta.cups_media or None)
        QTimer.singleShot(30000, self._show_idle)

    def _on_error(self, msg: str) -> None:
        log.error(msg)
        self._upload_status.setText(f"Error: {msg}")
        self._main_stack.setCurrentIndex(1)

    def _update_review_image(self) -> None:
        if self._review_source:
            self._review_image.set_source_pixmap(self._review_source)
        else:
            self._review_image.set_source_pixmap(None)

    def apply_display_mode(self) -> None:
        display = self.cfg.setdefault("display", {})
        if display.get("fullscreen", False):
            if not self.isFullScreen():
                self.showFullScreen()
        else:
            if self.isFullScreen():
                self.showNormal()
            w = int(display.get("width", 1024))
            h = int(display.get("height", 600))
            self.setMinimumSize(640, 400)
            self.resize(w, h)
            if not self.isVisible():
                self.show()
        self._sync_preview_chrome()

    def _persist_window_size(self) -> None:
        if self.isFullScreen():
            return
        display = self.cfg.setdefault("display", {})
        display["width"] = self.width()
        display["height"] = self.height()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._persist_window_size()
        self._sync_preview_chrome()
        self._update_review_image()

    def closeEvent(self, event) -> None:
        self._persist_window_size()
        save_config(self.cfg)
        self.camera.stop()
        self.flash.off()
        super().closeEvent(event)
