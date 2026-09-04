#!/bin/bash
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export QT_QPA_PLATFORM="${QT_QPA_PLATFORM:-eglfs}"
export QT_QPA_EGLFS_HIDECURSOR=1
export PYTHONPATH="$ROOT/src:${PYTHONPATH:-}"
cd "$ROOT"
exec python3 -m photobooth.main "$@"
