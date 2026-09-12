from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

log = logging.getLogger(__name__)


class CupsPrinter:
    def __init__(self, cfg: dict) -> None:
        print_cfg = cfg.get("print", {}) or {}
        self._queue = print_cfg.get("cups_queue", "") or ""
        # Default fit-to-page avoids spilling one sheet onto 2 pages when media ≠ pixels.
        self._fit_to_page = bool(print_cfg.get("fit_to_page", True))
        if sys.platform != "linux":
            raise RuntimeError("CUPS only on Linux")
        log.info(
            "Printer backend: CUPS queue=%r fit_to_page=%s",
            self._queue or "(empty)",
            self._fit_to_page,
        )

    def print_image(self, path: Path, media: str | None = None) -> bool:
        if not self._queue:
            log.error("CUPS print skipped — print.cups_queue is empty in config")
            return False
        if not path.is_file():
            log.error("CUPS print skipped — file missing: %s", path)
            return False
        cmd = ["lp", "-d", self._queue, "-n", "1"]
        if media:
            cmd.extend(["-o", f"media={media}"])
        if self._fit_to_page:
            cmd.extend(["-o", "fit-to-page"])
        else:
            cmd.extend(["-o", "fit-to-page=false"])
        cmd.append(str(path))
        log.info("CUPS print: %s", " ".join(cmd))
        try:
            r = subprocess.run(cmd, check=False, capture_output=True, text=True)
        except FileNotFoundError:
            log.error("CUPS print failed — `lp` not found (install cups)")
            return False
        except OSError as e:
            log.error("CUPS print failed: %s", e)
            return False
        if r.returncode != 0:
            err = (r.stderr or r.stdout or f"exit {r.returncode}").strip()
            log.error("CUPS print failed: %s", err)
            return False
        out = (r.stdout or "").strip()
        log.info("CUPS print OK%s", f": {out}" if out else "")
        return True

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
        ready = "ready" if self.is_ready() else "not ready / missing"
        return f"CUPS queue: {self._queue} ({ready})"

    def test_print(self, path: Path) -> bool:
        return self.print_image(path)
