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


def list_video_devices() -> list[str | int]:
    """Return candidate V4L2 device paths (preferred) or indices."""
    paths = sorted(Path("/dev").glob("video*"), key=lambda p: p.name)
    if paths:
        return [str(p) for p in paths]
    return list(range(0, 6))


def _fourcc_code(name: str) -> int:
    name = (name or "MJPG")[:4].ljust(4)
    return cv2.VideoWriter_fourcc(*name)


class V4l2Camera(CameraBackend):
    def __init__(self, cfg: dict) -> None:
        cam = cfg.get("camera", {})
        self._device_cfg = cam.get("device", "auto")
        self._fourcc = str(cam.get("fourcc", "MJPG") or "").strip()
        self._preview_size = tuple(cam.get("preview_size", [640, 480]))
        self._still_size = tuple(cam.get("still_size", [1920, 1080]))
        self._mirror = bool(cam.get("mirror", True))
        self._preview_fps = max(1, int(cam.get("preview_fps", 12)))
        self._opened_device: str | int | None = None
        self._opened_fourcc: str = self._fourcc or "MJPG"
        self._cap: Optional[cv2.VideoCapture] = None
        self._callback: Optional[Callable[[np.ndarray], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    def _device_candidates(self) -> list[str | int]:
        raw = self._device_cfg
        if raw in (None, "", "auto"):
            return list_video_devices()
        if isinstance(raw, str) and raw.startswith("/dev/"):
            rest = [d for d in list_video_devices() if d != raw]
            return [raw, *rest]
        try:
            idx = int(raw)
        except (TypeError, ValueError):
            log.warning("Invalid camera.device=%r, probing auto", raw)
            return list_video_devices()
        rest = [d for d in list_video_devices() if d != idx and d != f"/dev/video{idx}"]
        return [idx, *rest]

    def _fourcc_candidates(self) -> list[str]:
        preferred = self._fourcc.upper() if self._fourcc else "MJPG"
        out: list[str] = []
        for code in (preferred, "MJPG", "YUYV", "YUY2", ""):
            if code not in out:
                out.append(code)
        return out

    def _try_open(
        self,
        device: str | int,
        fourcc: str,
        size: tuple[int, int],
        *,
        verify_frame: bool = True,
    ) -> Optional[cv2.VideoCapture]:
        api = cv2.CAP_DSHOW if _is_windows() else cv2.CAP_V4L2
        cap = cv2.VideoCapture(device, api)
        if not cap.isOpened():
            cap.release()
            return None
        if fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, _fourcc_code(fourcc))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, size[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, size[1])
        try:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        if verify_frame:
            ok, frame = cap.read()
            if not ok or frame is None or getattr(frame, "size", 0) == 0:
                # Many Pi USB cams expose /dev/video0 as metadata-only.
                cap.release()
                return None
        return cap

    def _open(self, size: tuple[int, int] | None = None) -> cv2.VideoCapture:
        size = size or self._preview_size
        devices = self._device_candidates()
        fourccs = self._fourcc_candidates()
        log.info("Camera probe devices=%s fourccs=%s size=%s", devices, fourccs, size)

        # Prefer previously working combo when reopening for stills/preview restart.
        ordered_devices = list(devices)
        if self._opened_device is not None and self._opened_device in ordered_devices:
            ordered_devices.remove(self._opened_device)
            ordered_devices.insert(0, self._opened_device)

        last_err = "no candidates"
        for device in ordered_devices:
            for fourcc in fourccs:
                try:
                    cap = self._try_open(device, fourcc, size, verify_frame=True)
                except Exception as exc:
                    last_err = f"{device}/{fourcc or 'default'}: {exc}"
                    log.debug("Camera open failed %s", last_err)
                    continue
                if cap is None:
                    last_err = f"{device}/{fourcc or 'default'}: opened but no frames"
                    continue
                self._opened_device = device
                self._opened_fourcc = fourcc or "default"
                actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                log.info(
                    "Camera ready device=%s fourcc=%s requested=%sx%s actual=%sx%s",
                    device,
                    self._opened_fourcc,
                    size[0],
                    size[1],
                    actual_w,
                    actual_h,
                )
                return cap

        hint = (
            "Check: lsusb; ls -l /dev/video*; v4l2-ctl --list-devices; "
            "user in 'video' group; powered USB hub on Pi Zero."
        )
        raise RuntimeError(f"Cannot open camera ({last_err}). {hint}")

    def start_preview(self) -> None:
        if self._running:
            return
        self._cap = self._open(self._preview_size)
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
                    self._cap = None

            try:
                cap = self._open(self._still_size)
                for _ in range(5):
                    cap.read()
                ok, frame = cap.read()
                cap.release()
            except Exception:
                log.exception("Still capture open failed")
                ok, frame = False, None

            if was_running:
                self._running = True
                self._cap = self._open(self._preview_size)
                self._thread = threading.Thread(target=self._loop, daemon=True)
                self._thread.start()

        if not ok or frame is None:
            return False
        if self._mirror:
            frame = cv2.flip(frame, 1)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])


def _is_windows() -> bool:
    import sys

    return sys.platform == "win32"
