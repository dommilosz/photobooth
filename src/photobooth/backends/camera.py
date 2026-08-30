from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Optional

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

    @abstractmethod
    def capture_still(self, path: str) -> bool:
        ...


def create_camera(cfg: dict, mock: bool = False) -> CameraBackend:
    if mock:
        from photobooth.backends.mock_camera import MockCamera

        return MockCamera(cfg)
    from photobooth.backends.v4l2_camera import V4l2Camera

    return V4l2Camera(cfg)
