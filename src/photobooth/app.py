from __future__ import annotations

import sys

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication

from photobooth.backends.camera import create_camera
from photobooth.backends.flash import create_flash
from photobooth.backends.printer import create_printer
from photobooth.backends.upload import create_upload
from photobooth.compose.template_registry import TemplateRegistry
from photobooth.config import load_config
from photobooth.paths import ensure_data_dirs
from photobooth.ui.screens import PhotoboothApp
from photobooth.ui.theme import app_stylesheet


def run_app(cfg: dict, mock: bool = False, dev: bool = False) -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(app_stylesheet())
    ensure_data_dirs(cfg)
    registry = TemplateRegistry(cfg)
    camera = create_camera(cfg, mock=mock)
    flash = create_flash(cfg)
    printer = create_printer(cfg, dev=dev)
    upload = create_upload(cfg, dev=dev)
    window = PhotoboothApp(cfg, camera, flash, printer, upload, registry)
    window.apply_display_mode()
    return app.exec_()
