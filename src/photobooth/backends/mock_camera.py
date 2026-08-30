from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from photobooth.backends.camera import CameraBackend

log = logging.getLogger(__name__)


class MockCamera(CameraBackend):
    def __init__(self, cfg: dict) -> None:
        self._mirror = bool(cfg.get("camera", {}).get("mirror", True))
        self._callback: Optional[Callable[[np.ndarray], None]] = None
        self._running = False
        self._t0 = time.time()
        self._preview_size = tuple(cfg.get("camera", {}).get("preview_size", [640, 480]))

    def start_preview(self) -> None:
        self._running = True
        self._t0 = time.time()

    def stop(self) -> None:
        self._running = False

    def set_mirror(self, enabled: bool) -> None:
        self._mirror = enabled

    def set_frame_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        self._callback = callback

    def pump_frame(self) -> None:
        if not self._running or not self._callback:
            return
        w, h = self._preview_size
        t = time.time() - self._t0
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        for y in range(h):
            frame[y, :, 0] = int(128 + 127 * math.sin(t + y * 0.02))
            frame[y, :, 1] = int(128 + 127 * math.sin(t * 1.3 + y * 0.015))
            frame[y, :, 2] = int(128 + 127 * math.cos(t * 0.7))
        if self._mirror:
            frame = frame[:, ::-1, :]
        self._callback(frame)

    def capture_still(self, path: str) -> bool:
        w, h = (1920, 1080)
        frame = np.zeros((h, w, 3), dtype=np.uint8)
        frame[:, :] = (40, 80, 160)
        if self._mirror:
            frame = frame[:, ::-1, :]
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        import cv2

        return cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
