from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

import numpy as np


class CameraBackend(ABC):
    @abstractmethod
    def start_preview(self) -> None:
        ...

    @abstractmethod
    def stop(self) -> None:
        ...

    @abstractmethod
    def set_mirror(self, enabled: bool) -> None:
        ...

    @abstractmethod
    def set_frame_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        ...

    def prepare_still(self) -> None:
        """Do slow camera reopen / warm-up before flash. Optional."""

    def resume_preview(self) -> None:
        """Restore live preview after a still. Optional."""

    @abstractmethod
    def capture_still(self, path: str) -> bool:
        """Grab and save a still. Prefer prepare_still() first for flash sync."""


def create_camera(cfg: dict, mock: bool = False) -> CameraBackend:
    if mock:
        from photobooth.backends.mock_camera import MockCamera

        return MockCamera(cfg)
    from photobooth.backends.v4l2_camera import V4l2Camera

    return V4l2Camera(cfg)
