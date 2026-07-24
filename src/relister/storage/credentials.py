from __future__ import annotations

import json
from pathlib import Path

from relister.core.paths import credentials_path, ensure_writable
from relister.core.security import get_cipher


class CredentialStore:
    """Provider credentials stored as a single Fernet-encrypted JSON blob.

    Keyed by ``"<provider>|<role>"`` where role is ``source`` or
    ``destination``. Plaintext credentials never touch disk.
    """

    def __init__(self, path: Path | None = None) -> None:
        self._path = path or credentials_path()

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            raw = get_cipher().decrypt(self._path.read_bytes())
        except Exception:
            # Unreadable / key rotated: treat as empty rather than crash.
            return {}
        return json.loads(raw.decode("utf-8"))

    def _save(self, data: dict) -> None:
        ensure_writable()
        blob = get_cipher().encrypt(json.dumps(data).encode("utf-8"))
        self._path.write_bytes(blob)

    @staticmethod
    def _key(provider: str, role: str) -> str:
        return f"{provider}|{role}"

    def get(self, provider: str, role: str) -> tuple[str, str] | None:
        entry = self._load().get(self._key(provider, role))
        if not entry:
            return None
        return entry["username"], entry["password"]

    def set(self, provider: str, role: str, username: str, password: str) -> None:
        data = self._load()
        data[self._key(provider, role)] = {
            "username": username,
            "password": password,
        }
        self._save(data)

    def has(self, provider: str, role: str) -> bool:
        return self.get(provider, role) is not None
