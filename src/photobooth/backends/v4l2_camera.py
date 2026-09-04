from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from photobooth.backends.camera import CameraBackend

log = logging.getLogger(__name__)


class V4l2Camera(CameraBackend):
    def __init__(self, cfg: dict) -> None:
        cam = cfg.get("camera", {})
        self._device = int(cam.get("device", 0))
        self._fourcc = cam.get("fourcc", "MJPG")
        self._preview_size = tuple(cam.get("preview_size", [640, 480]))
        self._still_size = tuple(cam.get("still_size", [1920, 1080]))
        self._mirror = bool(cam.get("mirror", True))
        self._preview_fps = max(1, int(cam.get("preview_fps", 12)))
        self._cap: Optional[cv2.VideoCapture] = None
        self._callback: Optional[Callable[[np.ndarray], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    def _open(self) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(self._device, cv2.CAP_DSHOW if _is_windows() else cv2.CAP_V4L2)
        if self._fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self._fourcc[:4]))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._preview_size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._preview_size[1])
        # Prefer lower buffer latency when supported.
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        return cap

    def start_preview(self) -> None:
        if self._running:
            return
        self._cap = self._open()
        if not self._cap.isOpened():
            raise RuntimeError(f"Cannot open camera device {self._device}")
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        interval = 1.0 / float(self._preview_fps)
        next_frame = time.monotonic()
        while self._running and self._cap is not None:
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.02)
                continue
            if self._mirror:
                frame = cv2.flip(frame, 1)
            cb = self._callback
            if cb:
                cb(frame)
            now = time.monotonic()
            sleep_for = next_frame - now
            if sleep_for > 0:
                time.sleep(sleep_for)
            next_frame = time.monotonic() + interval

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._cap:
            self._cap.release()
            self._cap = None

    def set_mirror(self, enabled: bool) -> None:
        self._mirror = enabled

    def set_frame_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        self._callback = callback

    def capture_still(self, path: str) -> bool:
        with self._lock:
            was_running = self._running
            if was_running:
                self._running = False
                if self._thread:
                    self._thread.join(timeout=2)
                if self._cap:
                    self._cap.release()

            cap = self._open()
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._still_size[0])
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._still_size[1])
            for _ in range(5):
                cap.read()
            ok, frame = cap.read()
            cap.release()

            if was_running:
                self._running = True
                self._cap = self._open()
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()

        if not ok:
            return False
        if self._mirror:
            frame = cv2.flip(frame, 1)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])


def _is_windows() -> bool:
    import sys

    return sys.platform == "win32"
