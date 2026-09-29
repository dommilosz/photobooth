from __future__ import annotations

import logging
import sys
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class FlashBackend(ABC):
    def on(self, safety_ms: int | None = None) -> None:
        """Turn lamp on (optional safety auto-off)."""

    @abstractmethod
    def fire(self, warmup_ms: int, duration_ms: int) -> None:
        """Turn on flash, wait warmup; caller captures, then should call off()."""

    @abstractmethod
    def test_pulse(self, ms: int) -> None:
        ...

    @abstractmethod
    def off(self) -> None:
        ...


def create_flash(cfg: dict) -> FlashBackend:
    flash_cfg = cfg.get("flash", {})
    if not flash_cfg.get("enabled", True):
        from photobooth.backends.mock_flash import MockFlash

        return MockFlash()

    backend = str(flash_cfg.get("backend", "gpio")).strip().lower()
    if backend in ("serial", "usb", "usb_serial"):
        try:
            from photobooth.backends.serial_flash import SerialFlash

            return SerialFlash(flash_cfg)
        except Exception:
            log.exception("Serial flash init failed — using mock")
            from photobooth.backends.mock_flash import MockFlash

            return MockFlash()

    if backend == "mock" or (backend == "gpio" and sys.platform != "linux"):
        from photobooth.backends.mock_flash import MockFlash

        return MockFlash()

    try:
        from photobooth.backends.gpio_flash import GpioFlash

        return GpioFlash(flash_cfg)
    except Exception:
        log.exception("GPIO flash init failed — using mock")
        from photobooth.backends.mock_flash import MockFlash

        return MockFlash()
