# Phase 2 — Database, Credentials & At-Rest Encryption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Persist a listing-ID → images-folder mapping in SQLite (prefill on URL paste, save on Start, migrate old→new ID on relist), move provider credentials out of `.env` into a keychain-backed encrypted store edited via a per-provider gear dialog, and encrypt the browser session (hashed filename + encrypted contents).

**Architecture:** A Qt-free `core/paths.py` resolves the app-data dir. `core/security.py` holds a keyring-backed Fernet cipher + `hash_name`. `storage/` gets `database.py`, `property_images.py`, `credentials.py`. Providers gain `extract_listing_id`. `get_provider` reads the credential store. `browser/session.py` encrypts session state. `RelistPage` gains gear buttons + a credentials dialog and calls the repo at 3 points.

**Tech Stack:** Python 3.14, SQLite (stdlib), `cryptography` (Fernet), `keyring`, PySide6.

**Interpreter/tests:** `.venv/Scripts/python.exe`; `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest tests/ -q`.

---

## File structure (Phase 2)

```
src/relister/
  core/
    paths.py            # NEW  app-data dir resolver (Qt-free)
    security.py         # NEW  keyring-backed Fernet cipher + hash_name()
    config.py           # MODIFY  drop credential fields
  storage/
    database.py         # NEW  connection + schema init
    property_images.py  # NEW  PropertyImagesRepo
    credentials.py      # NEW  CredentialStore (Fernet-encrypted JSON)
  providers/
    base.py             # MODIFY  + extract_listing_id staticmethod
    factory.py          # MODIFY  read CredentialStore; + provider_class_for()
    zoopla/provider.py  # MODIFY  extract_listing_id override
  browser/session.py    # MODIFY  hashed filename + encrypted state
  gui/
    widgets/credentials_dialog.py  # NEW
    pages/relist_page.py           # MODIFY  gears + repo wiring
tests/
  test_paths.py                 # NEW
  test_security.py              # NEW
  storage/test_property_images.py    # NEW
  storage/test_credentials.py        # NEW
  providers/test_extract_listing_id.py  # NEW
  browser/test_session_encryption.py    # NEW
conftest.py             # NEW  force in-memory keyring backend for tests
```

Dependencies added to `pyproject.toml` core deps: `cryptography`, `keyring`.

---

### Task 1: pyproject deps + test keyring backend

- [ ] Add `"cryptography>=42"`, `"keyring>=24"` to `[project].dependencies`.
- [ ] Install: `.venv/Scripts/python.exe -m pip install cryptography keyring`.
- [ ] Create `tests/conftest.py` forcing an in-memory keyring so tests never touch the real keychain:
```python
import keyring
from keyring.backends.fail import Keyring as FailKeyring  # placeholder import guard

class _MemoryKeyring:
    priority = 1
    def __init__(self): self._d = {}
    def get_password(self, service, username): return self._d.get((service, username))
    def set_password(self, service, username, password): self._d[(service, username)] = password
    def delete_password(self, service, username): self._d.pop((service, username), None)

import pytest
@pytest.fixture(autouse=True)
def _mem_keyring():
    prev = keyring.get_keyring()
    keyring.set_keyring(_MemoryKeyring())
    yield
    keyring.set_keyring(prev)
```
- [ ] Commit `chore: add cryptography + keyring deps and test keyring backend`.

---

### Task 2: core/paths.py

**Test `tests/test_paths.py`:** monkeypatch env / platform → assert paths end with `AutoZoopla` and expected leaf names; `database_path()` under `data_dir()`.

- [ ] Implement:
```python
# src/relister/core/paths.py
from __future__ import annotations
import os, sys
from pathlib import Path

APP_NAME = "AutoZoopla"

def data_dir() -> Path:
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def database_path() -> Path: return data_dir() / "relister.db"
def credentials_path() -> Path: return data_dir() / "credentials.enc"

def browser_states_dir() -> Path:
    d = data_dir() / "browser_states"; d.mkdir(parents=True, exist_ok=True); return d

def browser_cache_dir() -> Path:
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    return Path(override) if override else data_dir() / "ms-playwright"
```
- [ ] Test + commit `feat(core): add app-data path resolver`.

---

### Task 3: core/security.py

**Test `tests/test_security.py`:** with the in-memory keyring: `get_cipher()` round-trips (`decrypt(encrypt(b"x")) == b"x"`); two calls reuse the same key; `hash_name("a","b")` is stable, hex, and differs for different inputs.

- [ ] Implement:
```python
# src/relister/core/security.py
from __future__ import annotations
import hashlib, hmac, base64
import keyring
from cryptography.fernet import Fernet

_SERVICE = "AutoZoopla"
_KEY_NAME = "encryption-key"

def _get_or_create_key() -> bytes:
    existing = keyring.get_password(_SERVICE, _KEY_NAME)
    if existing:
        return existing.encode("ascii")
    key = Fernet.generate_key()
    keyring.set_password(_SERVICE, _KEY_NAME, key.decode("ascii"))
    return key

def get_cipher() -> Fernet:
    return Fernet(_get_or_create_key())

def hash_name(*parts: str) -> str:
    key = _get_or_create_key()  # Fernet key doubles as HMAC secret
    msg = "|".join(parts).encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()[:32]
```
- [ ] Test + commit `feat(core): add keyring-backed cipher and hash_name`.

---

### Task 4: storage/database.py + PropertyImagesRepo

**Test `tests/storage/test_property_images.py`:** using a `tmp_path` db → set/get; upsert overwrites + bumps updated_at; `get` unknown → None; `migrate_id(old,new)` moves the row; migrate when `new` already exists replaces it; migrate when `old` absent is a no-op.

- [ ] `database.py`:
```python
# src/relister/storage/database.py
from __future__ import annotations
import sqlite3
from pathlib import Path
from relister.core.paths import database_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS property_images (
    listing_id TEXT PRIMARY KEY,
    images_dir TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or database_path())
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
```
- [ ] `property_images.py`:
```python
# src/relister/storage/property_images.py
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from .database import connect, init_schema

class PropertyImagesRepo:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path
        with connect(self._db_path) as conn:
            init_schema(conn)

    def get_images_dir(self, listing_id: str) -> str | None:
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT images_dir FROM property_images WHERE listing_id = ?",
                (listing_id,),
            ).fetchone()
        return row[0] if row else None

    def set_images_dir(self, listing_id: str, images_dir: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO property_images(listing_id, images_dir, updated_at) "
                "VALUES(?,?,?) ON CONFLICT(listing_id) DO UPDATE SET "
                "images_dir=excluded.images_dir, updated_at=excluded.updated_at",
                (listing_id, images_dir, now),
            )
            conn.commit()

    def migrate_id(self, old_id: str, new_id: str) -> None:
        if old_id == new_id:
            return
        now = datetime.now(timezone.utc).isoformat()
        with connect(self._db_path) as conn:
            row = conn.execute(
                "SELECT images_dir FROM property_images WHERE listing_id = ?",
                (old_id,),
            ).fetchone()
            if row is None:
                return
            conn.execute("DELETE FROM property_images WHERE listing_id = ?", (new_id,))
            conn.execute(
                "UPDATE property_images SET listing_id = ?, updated_at = ? WHERE listing_id = ?",
                (new_id, now, old_id),
            )
            conn.commit()
```
- [ ] Test + commit `feat(storage): add PropertyImagesRepo`.

---

### Task 5: CredentialStore

**Test `tests/storage/test_credentials.py`:** (in-memory keyring, tmp path) set/get round-trips; `has` reflects presence; get unknown → None; the on-disk file is not plaintext (does not contain the password).

- [ ] Implement:
```python
# src/relister/storage/credentials.py
from __future__ import annotations
import json
from pathlib import Path
from relister.core.paths import credentials_path
from relister.core.security import get_cipher

class CredentialStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or credentials_path()

    def _load(self) -> dict:
        if not self._path.exists():
            return {}
        try:
            raw = get_cipher().decrypt(self._path.read_bytes())
        except Exception:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _save(self, data: dict) -> None:
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
        data[self._key(provider, role)] = {"username": username, "password": password}
        self._save(data)

    def has(self, provider: str, role: str) -> bool:
        return self.get(provider, role) is not None
```
- [ ] Test + commit `feat(storage): add encrypted CredentialStore`.

---

### Task 6: Provider extract_listing_id + factory wiring

**Test `tests/providers/test_extract_listing_id.py`:** `ZooplaProvider.extract_listing_id("https://pro.zoopla.co.uk/properties/listing/5356300") == "5356300"`; trailing slash and `?query` handled; base `PropertyProvider.extract_listing_id` returns last segment too (default).

- [ ] `base.py`: add
```python
    @staticmethod
    def extract_listing_id(url: str) -> str | None:
        url = str(url).rstrip("/")
        if not url:
            return None
        return url.split("/")[-1].split("?")[0] or None
```
- [ ] `zoopla/provider.py`: add same as an explicit override (documents Zoopla URL shape) and refactor `create_listing_page.extract_listing_id` to delegate to it.
- [ ] `factory.py`: read from `CredentialStore`:
```python
from relister.storage.credentials import CredentialStore
def get_provider(name: str, *, destination: bool = False) -> PropertyProvider:
    role = "destination" if destination else "source"
    store = CredentialStore()
    creds = store.get(name.lower(), role) or ("", "")
    providers = {"zoopla": lambda: ZooplaProvider(username=creds[0], password=creds[1])}
    try:
        return providers[name.lower()]()
    except KeyError as exc:
        raise ValueError(f"Unsupported provider: {name}. Supported providers: {', '.join(providers)}") from exc

def provider_class_for(name: str):
    return {"zoopla": ZooplaProvider}.get(name.lower())
```
- [ ] Test + commit `feat(providers): id extraction + credential-store-backed factory`.

---

### Task 7: config.py — drop credential fields + .env migration

- [ ] Remove `zoopla_*`/`onthemarket_*` fields from `Settings`. Add a one-time importer:
```python
# src/relister/core/config.py
from __future__ import annotations
import os
from pathlib import Path
from relister.storage.credentials import CredentialStore

def migrate_env_credentials(store: CredentialStore | None = None) -> None:
    """One-time import of legacy .env credentials into the encrypted store."""
    store = store or CredentialStore()
    mapping = {
        ("zoopla", "source"): ("ZOOPLA_SOURCE_USERNAME", "ZOOPLA_SOURCE_PASSWORD"),
        ("zoopla", "destination"): ("ZOOPLA_DESTINATION_USERNAME", "ZOOPLA_DESTINATION_PASSWORD"),
    }
    env = _read_env_file(Path(".env"))
    for (provider, role), (u_key, p_key) in mapping.items():
        if store.has(provider, role):
            continue
        u = env.get(u_key) or os.environ.get(u_key)
        p = env.get(p_key) or os.environ.get(p_key)
        if u and p:
            store.set(provider, role, u, p)

def _read_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        result[k.strip().upper()] = v.strip().strip('"').strip("'")
    return result
```
- [ ] Call `migrate_env_credentials()` once at GUI startup (`app.main`) guarded by try/except.
- [ ] Update `.env.example` + README note. Commit `refactor(core): move credentials to encrypted store, drop .env creds`.

---

### Task 8: Session encryption

**Test `tests/browser/test_session_encryption.py`:** helper functions `save_state(dir, name, dict)` writes a `.enc` file whose bytes ≠ JSON; `load_state` returns the same dict; missing file → None. (Filename via `hash_name`.)

- [ ] Refactor `browser/session.py`: introduce `_session_file(self)` → `paths.browser_states_dir() / (hash_name(provider.name, alias) + ".enc")`. `_save_session_state` uses `context.storage_state()` (dict) → `get_cipher().encrypt(json)`. Context creation loads + decrypts to a dict for `storage_state=`. Also add the Firefox→WebKit launch fallback here (Phase 3 will also touch this; keep the helper).
- [ ] Test the pure save/load helpers + commit `feat(browser): encrypt session state with hashed filenames`.

---

### Task 9: Gear UI + CredentialsDialog + repo wiring in RelistPage

- [ ] `gui/widgets/credentials_dialog.py`: `CredentialsDialog(QDialog)` with provider/role, username + password (masked, reveal toggle), Save/Cancel; `load(store)` prefill; on Save `store.set(...)`.
- [ ] `RelistPage.__init__` gains `repo: PropertyImagesRepo` and `credentials: CredentialStore` params. Add a gear `QToolButton` next to each provider combo (`_add_gear`), opening the dialog for that combo's current provider + role.
- [ ] URL flow: on `url_edit.textChanged` (debounced or immediate), extract id via `provider_class_for(source).extract_listing_id`; if a mapping exists and images field empty → prefill + status hint.
- [ ] Start flow: in `_start_relist`, after building request, if `images_path`: `repo.set_images_dir(id, str(images_path))`.
- [ ] Success flow: in `_on_success`, if `result.published` and `result.destination_listing_url`: `repo.migrate_id(old_id, new_id)`.
- [ ] `MainWindow` constructs `PropertyImagesRepo()` + `CredentialStore()` and injects them.
- [ ] Smoke: launch offscreen, open dialog, simulate url change with a seeded repo → images prefilled. Commit `feat(gui): credential gear dialog + DB prefill/save/migrate`.

---

## Self-review
- Credentials never written plaintext; `.env` no longer read by `Settings`.
- Repo migrate covers new-id-exists + old-absent.
- Session file name reveals nothing; contents encrypted; missing/garbage file → fresh login.
- GUI+CLI both use the new factory.
