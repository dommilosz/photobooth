from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class PrinterBackend(ABC):
    @abstractmethod
    def print_image(self, path: Path, media: str | None = None) -> bool:
        ...

    @abstractmethod
    def is_ready(self) -> bool:
        ...

    @abstractmethod
    def status_message(self) -> str:
        ...

    @abstractmethod
    def test_print(self, path: Path) -> bool:
        ...


def create_printer(cfg: dict, dev: bool = False) -> PrinterBackend:
    if dev:
        from photobooth.backends.file_printer import FilePrinter

        return FilePrinter(cfg)
    try:
        from photobooth.backends.cups_printer import CupsPrinter

        return CupsPrinter(cfg)
    except Exception:
        from photobooth.backends.file_printer import FilePrinter

        return FilePrinter(cfg)
