from __future__ import annotations

from photobooth.backends.camera import CameraBackend, create_camera


class CameraService:
    """Thin wrapper over CameraBackend."""

    def __init__(self, cfg: dict, mock: bool = False) -> None:
        self._backend = create_camera(cfg, mock=mock)

    @property
    def backend(self) -> CameraBackend:
        return self._backend

    def start_preview(self) -> None:
        self._backend.start_preview()

    def stop(self) -> None:
        self._backend.stop()

    def set_mirror(self, enabled: bool) -> None:
        self._backend.set_mirror(enabled)

    def set_frame_callback(self, callback) -> None:
        self._backend.set_frame_callback(callback)

    def capture_still(self, path: str) -> bool:
        return self._backend.capture_still(path)
