from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)


class MockUpload:
    def __init__(self, cfg: dict) -> None:
        self._cfg = cfg

    def upload_session(self, session_id: str, files: dict[str, Path]) -> bool:
        for name, path in files.items():
            log.info("Mock upload %s → %s (%s)", session_id, name, path)
        return True

    def test_connection(self) -> bool:
        log.info("Mock upload test OK")
        return True

    def retry_pending(self) -> int:
        return 0
