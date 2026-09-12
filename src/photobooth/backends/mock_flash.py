from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger(__name__)


class MockFlash:
    def on(self, safety_ms: int | None = None) -> None:
        log.info("FLASH ON (safety=%s)", safety_ms)

    def fire(self, warmup_ms: int, duration_ms: int) -> None:
        log.info("FLASH ON (warmup %dms, safety %dms)", warmup_ms, duration_ms)
        self.on(safety_ms=max(duration_ms, warmup_ms + 1500))
        if warmup_ms > 0:
            time.sleep(warmup_ms / 1000.0)

    def test_pulse(self, ms: int) -> None:
        log.info("FLASH TEST %dms", ms)
        threading.Timer(ms / 1000.0, self.off).start()

    def off(self) -> None:
        log.info("FLASH OFF")
