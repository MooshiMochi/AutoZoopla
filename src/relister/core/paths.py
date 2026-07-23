from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "AutoZoopla"


def data_dir() -> Path:
    """Return (creating if needed) the per-user app-data directory.

    Qt-free so the CLI and browser session can use it without a running
    ``QApplication``.
    """

    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def database_path() -> Path:
    return data_dir() / "relister.db"


def credentials_path() -> Path:
    return data_dir() / "credentials.enc"


def browser_states_dir() -> Path:
    directory = data_dir() / "browser_states"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def browser_cache_dir() -> Path:
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    return Path(override) if override else data_dir() / "ms-playwright"
