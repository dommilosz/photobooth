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
        # Hard safety so the lamp never sticks on if capture hangs.
        self._safety_ms = int(cfg.get("safety_ms", 5000))
        atexit.register(self.off)

    def on(self, safety_ms: int | None = None) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._device.on()
        limit = self._safety_ms if safety_ms is None else max(100, int(safety_ms))
        self._timer = threading.Timer(limit / 1000.0, self.off)
        self._timer.daemon = True
        self._timer.start()

    def fire(self, warmup_ms: int, duration_ms: int) -> None:
        """Turn on, wait warmup; caller should capture then call off().

        duration_ms is used as a safety timeout (lamp auto-off), not as a fixed
        flash pulse length — USB still capture is often slower than a short pulse.
        """
        safety = max(int(duration_ms), int(warmup_ms) + 1500, self._safety_ms)
        self.on(safety_ms=safety)
        if warmup_ms > 0:
            time.sleep(warmup_ms / 1000.0)

    def test_pulse(self, ms: int) -> None:
        self.on(safety_ms=ms)
        # Replace safety timer with exact pulse length.
        if self._timer:
            self._timer.cancel()
        self._timer = threading.Timer(ms / 1000.0, self.off)
        self._timer.daemon = True
        self._timer.start()

    def off(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None
        self._device.off()
