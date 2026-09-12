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
        self._still_warmup_frames = max(1, int(cam.get("still_warmup_frames", 3)))
        self._opened_device: str | int | None = None
        self._opened_fourcc: str = self._fourcc or "MJPG"
        self._cap: Optional[cv2.VideoCapture] = None
        self._still_cap: Optional[cv2.VideoCapture] = None
        self._callback: Optional[Callable[[np.ndarray], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._still_armed = False
        self._lock = threading.Lock()
        self._was_preview_running = False

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

    def _open_fast(self, size: tuple[int, int]) -> cv2.VideoCapture:
        """Prefer the last working device/fourcc — much faster than a full probe."""
        if self._opened_device is not None:
            fourcc = "" if self._opened_fourcc in ("", "default") else self._opened_fourcc
            try:
                cap = self._try_open(self._opened_device, fourcc, size, verify_frame=True)
            except Exception:
                cap = None
            if cap is not None:
                actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                log.info(
                    "Camera fast-open device=%s fourcc=%s requested=%sx%s actual=%sx%s",
                    self._opened_device,
                    self._opened_fourcc,
                    size[0],
                    size[1],
                    actual_w,
                    actual_h,
                )
                return cap
        return self._open(size)

    def start_preview(self) -> None:
        with self._lock:
            if self._running:
                return
            self._start_preview_locked()

    def _loop(self) -> None:
        interval = 1.0 / float(self._preview_fps)
        next_frame = time.monotonic()
        fail_streak = 0
        while self._running:
            cap = self._cap
            if cap is None:
                time.sleep(0.05)
                continue
            try:
                ok, frame = cap.read()
            except cv2.error as exc:
                fail_streak += 1
                log.warning("Camera read error (%s); streak=%d", exc, fail_streak)
                ok, frame = False, None
            if not ok or frame is None or getattr(frame, "size", 0) == 0:
                fail_streak += 1
                if fail_streak >= 8:
                    self._reconnect_preview()
                    fail_streak = 0
                else:
                    time.sleep(0.05)
                continue
            fail_streak = 0
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

    def _reconnect_preview(self) -> None:
        log.warning("Reconnecting camera preview…")
        old = self._cap
        self._cap = None
        if old is not None:
            try:
                old.release()
            except Exception:
                pass
        try:
            self._cap = self._open_fast(self._preview_size)
            log.info("Camera reconnected")
        except Exception:
            log.exception("Camera reconnect failed")
            time.sleep(0.5)

    def set_mirror(self, enabled: bool) -> None:
        self._mirror = enabled

    def set_frame_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        self._callback = callback

    def _stop_preview_locked(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def _start_preview_locked(self) -> None:
        self._cap = self._open_fast(self._preview_size)
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def prepare_still(self) -> None:
        """Stop preview, open still resolution, warm up frames — before flash."""
        with self._lock:
            t0 = time.monotonic()
            self._was_preview_running = self._running or self._cap is not None
            if self._running or self._thread or self._cap:
                self._stop_preview_locked()
            if self._still_cap is not None:
                try:
                    self._still_cap.release()
                except Exception:
                    pass
                self._still_cap = None
            try:
                cap = self._open_fast(self._still_size)
                for _ in range(self._still_warmup_frames):
                    cap.read()
                self._still_cap = cap
                self._still_armed = True
                log.info("Still prepared in %.0fms", (time.monotonic() - t0) * 1000.0)
            except Exception:
                self._still_armed = False
                self._still_cap = None
                log.exception("Still prepare failed")
                if self._was_preview_running:
                    try:
                        self._start_preview_locked()
                    except Exception:
                        log.exception("Preview restore after prepare failure failed")
                raise

    def resume_preview(self) -> None:
        with self._lock:
            if self._still_cap is not None:
                try:
                    self._still_cap.release()
                except Exception:
                    pass
                self._still_cap = None
            self._still_armed = False
            if self._was_preview_running and not self._running:
                try:
                    self._start_preview_locked()
                except Exception:
                    log.exception("Preview resume failed")
            self._was_preview_running = False

    def capture_still(self, path: str) -> bool:
        with self._lock:
            armed = self._still_armed and self._still_cap is not None
            if armed:
                cap = self._still_cap
                assert cap is not None
                t0 = time.monotonic()
                try:
                    # One flush + grab keeps latency low while avoiding a stale buffer frame.
                    cap.read()
                    ok, frame = cap.read()
                except Exception:
                    log.exception("Armed still grab failed")
                    ok, frame = False, None
                log.info("Still grab took %.0fms", (time.monotonic() - t0) * 1000.0)
            else:
                was_running = self._running
                if was_running or self._thread or self._cap:
                    self._stop_preview_locked()
                try:
                    cap = self._open_fast(self._still_size)
                    for _ in range(self._still_warmup_frames):
                        cap.read()
                    ok, frame = cap.read()
                    cap.release()
                except Exception:
                    log.exception("Still capture open failed")
                    ok, frame = False, None
                if was_running:
                    try:
                        self._start_preview_locked()
                    except Exception:
                        log.exception("Preview restart after still failed")

        if not ok or frame is None:
            return False
        if self._mirror:
            frame = cv2.flip(frame, 1)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return cv2.imwrite(path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._still_cap:
            self._still_cap.release()
            self._still_cap = None
            self._still_armed = False
        if self._cap:
            self._cap.release()
            self._cap = None


def _is_windows() -> bool:
    import sys

    return sys.platform == "win32"
