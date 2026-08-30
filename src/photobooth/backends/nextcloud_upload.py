from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from photobooth.paths import app_root

log = logging.getLogger(__name__)


def extract_share_token(share_url: str) -> str:
    m = re.search(r"/s/([A-Za-z0-9]+)", share_url)
    if not m:
        raise ValueError(f"Cannot parse share token from URL: {share_url}")
    return m.group(1)


class NextcloudUpload:
    def __init__(self, cfg: dict) -> None:
        u = cfg.get("upload", {})
        self._share_url = u.get("share_url", "")
        self._password = u.get("password", "") or ""
        self._token = extract_share_token(self._share_url)
        parsed = urlparse(self._share_url)
        self._base = f"{parsed.scheme}://{parsed.netloc}/public.php/dav/files/{self._token}/"
        self._auth = (self._token, self._password)
        self._headers = {
            "X-Requested-With": "XMLHttpRequest",
        }
        rel = cfg.get("paths", {}).get("upload_queue_dir", "data/upload_queue")
        self._queue_dir = app_root() / rel
        self._queue_dir.mkdir(parents=True, exist_ok=True)

    def _put(self, remote_name: str, data: bytes, nickname: str) -> bool:
        url = f"{self._base}{remote_name}"
        headers = {**self._headers, "X-NC-Nickname": nickname}
        r = requests.put(url, data=data, auth=self._auth, headers=headers, timeout=60)
        if r.status_code not in (200, 201, 204):
            log.error("Upload %s failed: %d %s", remote_name, r.status_code, r.text[:200])
            return False
        return True

    def upload_session(self, session_id: str, files: dict[str, Path]) -> bool:
        ok_all = True
        for name, path in files.items():
            if not path.is_file():
                continue
            data = path.read_bytes()
            if not self._put(name, data, session_id):
                self._enqueue(session_id, name, path)
                ok_all = False
        return ok_all

    def _enqueue(self, session_id: str, name: str, path: Path) -> None:
        dest = self._queue_dir / f"{session_id}_{name}"
        shutil.copy2(path, dest)
        meta = self._queue_dir / f"{session_id}_{name}.json"
        meta.write_text(json.dumps({"session_id": session_id, "name": name}), encoding="utf-8")

    def retry_pending(self) -> int:
        count = 0
        for meta in self._queue_dir.glob("*.json"):
            info = json.loads(meta.read_text(encoding="utf-8"))
            data_path = self._queue_dir / f"{info['session_id']}_{info['name']}"
            if data_path.is_file() and self._put(
                info["name"], data_path.read_bytes(), info["session_id"]
            ):
                data_path.unlink(missing_ok=True)
                meta.unlink(missing_ok=True)
                count += 1
        return count

    def test_connection(self) -> bool:
        name = f"photobooth_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        return self._put(name, b"photobooth test", f"test_{datetime.now().strftime('%H%M%S')}")
