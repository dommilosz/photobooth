from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running from source without install
_SRC = Path(__file__).resolve().parents[1]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from photobooth.config import load_config
from photobooth.ui.vkb_env import enable_qt_virtual_keyboard


def _bootstrap_virtual_keyboard(config_path: Path | None) -> None:
    cfg = load_config(config_path)
    if cfg.get("ui", {}).get("virtual_keyboard", True):
        enable_qt_virtual_keyboard()


from photobooth.app import run_app


def main() -> None:
    parser = argparse.ArgumentParser(description="Photobooth")
    parser.add_argument("--mock", action="store_true", help="Use mock camera")
    parser.add_argument("--dev", action="store_true", help="Dev mode: save prints to disk instead of CUPS")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _bootstrap_virtual_keyboard(args.config)
    cfg = load_config(args.config)
    sys.exit(run_app(cfg, mock=args.mock, dev=args.dev))


if __name__ == "__main__":
    main()
