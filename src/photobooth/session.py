from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from photobooth.backends.camera import CameraBackend
from photobooth.backends.flash import FlashBackend

log = logging.getLogger(__name__)


class CaptureSession(QObject):
    countdown_tick = pyqtSignal(int)
    flash_fired = pyqtSignal()
    photo_taken = pyqtSignal(int, str)
    session_complete = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(
        self,
        camera: CameraBackend,
        flash: FlashBackend,
        session_dir: Path,
        photo_count: int,
        countdown_seconds: int,
        inter_photo_pause_ms: int,
        flash_warmup_ms: int,
        flash_duration_ms: int,
    ) -> None:
        super().__init__()
        self._camera = camera
        self._flash = flash
        self._session_dir = session_dir
        self._photo_count = photo_count
        self._countdown = countdown_seconds
        self._pause_ms = inter_photo_pause_ms
        self._warmup = flash_warmup_ms
        self._duration = flash_duration_ms
        self._paths: list[str] = []

    def run(self) -> None:
        self._session_dir.mkdir(parents=True, exist_ok=True)
        self._paths = []
        try:
            for i in range(self._photo_count):
                # Countdown: do slow camera arming during the last "1",
                # so tick 0 = flash + shutter (not prepare).
                for t in range(self._countdown, 0, -1):
                    self.countdown_tick.emit(t)
                    if t == 1:
                        t0 = time.monotonic()
                        self._camera.prepare_still()
                        log.info(
                            "Photo %d prepare_still during countdown-1: %.0fms",
                            i + 1,
                            (time.monotonic() - t0) * 1000.0,
                        )
                        remaining = 1.0 - (time.monotonic() - t0)
                        if remaining > 0:
                            time.sleep(remaining)
                    else:
                        time.sleep(1)

                path = str(self._session_dir / f"photo_{i + 1:02d}.jpg")
                ok = False
                try:
                    self.countdown_tick.emit(0)
                    self._flash.fire(self._warmup, self._duration)
                    self.flash_fired.emit()
                    t1 = time.monotonic()
                    ok = self._camera.capture_still(path)
                    log.info(
                        "Photo %d shutter at countdown-0: %.0fms ok=%s",
                        i + 1,
                        (time.monotonic() - t1) * 1000.0,
                        ok,
                    )
                finally:
                    self._flash.off()
                    self._camera.resume_preview()

                if not ok:
                    self.error.emit(f"Failed to capture photo {i + 1}")
                    return
                self._paths.append(path)
                self.photo_taken.emit(i + 1, path)
                if i < self._photo_count - 1:
                    time.sleep(self._pause_ms / 1000.0)
            self.session_complete.emit(self._paths)
        except Exception as e:
            log.exception("Capture session failed")
            try:
                self._flash.off()
            except Exception:
                pass
            try:
                self._camera.resume_preview()
            except Exception:
                pass
            self.error.emit(str(e))


class SessionWorker(QThread):
    def __init__(self, session: CaptureSession) -> None:
        super().__init__()
        self._session = session

    def run(self) -> None:
        self._session.run()


def make_session_id(event_name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in event_name)
    return f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
