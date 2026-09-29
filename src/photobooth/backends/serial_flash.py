from __future__ import annotations

import atexit
import logging
import threading
import time

log = logging.getLogger(__name__)


class SerialFlash:
    """USB serial lamp controller.

    Sends ASCII commands ``D <power>\\n`` (on) and ``D 0\\n`` (off).
    """

    def __init__(self, cfg: dict) -> None:
        import serial

        port = str(cfg.get("serial_port") or cfg.get("port") or "").strip()
        if not port:
            raise ValueError("flash.serial_port is required for backend=serial")
        baud = int(cfg.get("serial_baud", cfg.get("baudrate", 115200)))
        self._power = max(0, int(cfg.get("power", 100)))
        self._off_power = max(0, int(cfg.get("off_power", 0)))
        self._safety_ms = int(cfg.get("safety_ms", 5000))
        self._lock = threading.Lock()
        self._timer: threading.Timer | None = None
        self._ser = serial.Serial(
            port=port,
            baudrate=baud,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1.0,
            write_timeout=1.0,
        )
        # Give USB-CDC adapters a moment after open.
        time.sleep(0.15)
        self.off()
        atexit.register(self.off)
        log.info(
            "SerialFlash ready port=%s baud=%s power=%s",
            port,
            baud,
            self._power,
        )

    def _send(self, power: int) -> None:
        line = f"D {int(power)}\n".encode("ascii", errors="ignore")
        with self._lock:
            if self._ser is None or not self._ser.is_open:
                raise RuntimeError("Serial flash port is not open")
            self._ser.write(line)
            self._ser.flush()
        log.debug("SerialFlash → %r", line)

    def _cancel_timer(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def on(self, safety_ms: int | None = None) -> None:
        self._cancel_timer()
        self._send(self._power)
        limit = self._safety_ms if safety_ms is None else max(100, int(safety_ms))
        self._timer = threading.Timer(limit / 1000.0, self.off)
        self._timer.daemon = True
        self._timer.start()

    def fire(self, warmup_ms: int, duration_ms: int) -> None:
        safety = max(int(duration_ms), int(warmup_ms) + 1500, self._safety_ms)
        self.on(safety_ms=safety)
        if warmup_ms > 0:
            time.sleep(warmup_ms / 1000.0)

    def test_pulse(self, ms: int) -> None:
        self.on(safety_ms=ms)
        self._cancel_timer()
        self._timer = threading.Timer(ms / 1000.0, self.off)
        self._timer.daemon = True
        self._timer.start()

    def off(self) -> None:
        self._cancel_timer()
        try:
            self._send(self._off_power)
        except Exception:
            log.exception("SerialFlash off failed")
