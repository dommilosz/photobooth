from __future__ import annotations

import logging
import threading
import time

log = logging.getLogger(__name__)


class MockFlash:
    def fire(self, warmup_ms: int, duration_ms: int) -> None:
        log.info("FLASH ON (warmup %dms)", warmup_ms)
        time.sleep(warmup_ms / 1000.0)
        threading.Timer(duration_ms / 1000.0, self.off).start()

    def test_pulse(self, ms: int) -> None:
        log.info("FLASH TEST %dms", ms)
        threading.Timer(ms / 1000.0, self.off).start()

    def off(self) -> None:
        log.info("FLASH OFF")
