from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

from photobooth.paths import app_root

log = logging.getLogger(__name__)


class FilePrinter:
    def __init__(self, cfg: dict) -> None:
        rel = cfg.get("paths", {}).get("prints_dir", "data/prints")
        self._out = app_root() / rel
        self._out.mkdir(parents=True, exist_ok=True)

    def print_image(self, path: Path, media: str | None = None) -> bool:
        dest = self._out / f"print_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{path.name}"
        shutil.copy2(path, dest)
        log.info("Saved print job to %s", dest)
        return True

    def is_ready(self) -> bool:
        return True

    def status_message(self) -> str:
        return f"File printer → {self._out}"

    def test_print(self, path: Path) -> bool:
        return self.print_image(path)
