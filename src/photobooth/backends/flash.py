from __future__ import annotations

from abc import ABC, abstractmethod


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
    import sys

    flash_cfg = cfg.get("flash", {})
    if not flash_cfg.get("enabled", True) or sys.platform != "linux":
        from photobooth.backends.mock_flash import MockFlash

        return MockFlash()
    try:
        from photobooth.backends.gpio_flash import GpioFlash

        return GpioFlash(flash_cfg)
    except Exception:
        from photobooth.backends.mock_flash import MockFlash

        return MockFlash()
