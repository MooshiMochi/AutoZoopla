from __future__ import annotations

import json
from pathlib import Path

from relister.core.paths import data_dir


class AppSettings:
    """Plain (non-secret) app settings persisted as JSON in the app-data dir.

    Qt-free so provider/browser code can read it without a running
    ``QApplication``. Secrets belong in :class:`~relister.storage.credentials.CredentialStore`,
    not here.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or (data_dir() / "settings.json")

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def get(self, key: str, default: str | None = None) -> str | None:
        value = self._load().get(key)
        return value if value is not None else default

    def set(self, key: str, value: str) -> None:
        data = self._load()
        data[key] = value
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
