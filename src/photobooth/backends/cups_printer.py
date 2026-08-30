from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


class CupsPrinter:
    def __init__(self, cfg: dict) -> None:
        self._queue = cfg.get("print", {}).get("cups_queue", "")
        if sys.platform != "linux":
            raise RuntimeError("CUPS only on Linux")

    def print_image(self, path: Path, media: str | None = None) -> bool:
        cmd = ["lp", "-d", self._queue]
        if media:
            cmd.extend(["-o", f"media={media}"])
        cmd.extend(["-o", "fit-to-page=false", str(path)])
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return True
        except subprocess.CalledProcessError as e:
            log.error("CUPS print failed: %s", e.stderr)
            return False

    def is_ready(self) -> bool:
        if not self._queue:
            return False
        try:
            r = subprocess.run(
                ["lpstat", "-p", self._queue],
                capture_output=True,
                text=True,
                check=False,
            )
            return r.returncode == 0 and "disabled" not in (r.stdout or "").lower()
        except FileNotFoundError:
            return False

    def status_message(self) -> str:
        if not self._queue:
            return "No printer queue configured"
        return f"CUPS queue: {self._queue}"

    def test_print(self, path: Path) -> bool:
        return self.print_image(path)
