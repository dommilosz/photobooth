from __future__ import annotations

from pathlib import Path

from photobooth.backends.printer import PrinterBackend


def print_image(printer: PrinterBackend, path: Path, media: str | None = None) -> bool:
    return printer.print_image(path, media)
