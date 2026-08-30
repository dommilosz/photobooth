from __future__ import annotations

import atexit
import threading
import time


class GpioFlash:
    def __init__(self, cfg: dict) -> None:
        from gpiozero import OutputDevice

        pin = int(cfg.get("gpio_pin", 17))
        active_high = bool(cfg.get("active_high", True))
        self._device = OutputDevice(pin, active_high=active_high, initial_value=False)
        self._timer: threading.Timer | None = None
        atexit.register(self.off)

    def fire(self, warmup_ms: int, duration_ms: int) -> None:
        self._device.on()
        time.sleep(warmup_ms / 1000.0)

        def _off():
            self._device.off()

        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(duration_ms / 1000.0, _off)
        self._timer.start()

    def test_pulse(self, ms: int) -> None:
        self._device.on()
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(ms / 1000.0, self.off)
        self._timer.start()

    def off(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._device.off()
