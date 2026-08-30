from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class UploadBackend(ABC):
    @abstractmethod
    def upload_session(self, session_id: str, files: dict[str, Path]) -> bool:
        ...

    @abstractmethod
    def test_connection(self) -> bool:
        ...

    @abstractmethod
    def retry_pending(self) -> int:
        ...


def create_upload(cfg: dict, dev: bool = False) -> UploadBackend:
    upload_cfg = cfg.get("upload", {})
    if not upload_cfg.get("enabled", True):
        from photobooth.backends.mock_upload import MockUpload

        return MockUpload(cfg)
    from photobooth.backends.nextcloud_upload import NextcloudUpload

    return NextcloudUpload(cfg)
