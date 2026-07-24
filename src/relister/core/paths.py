from __future__ import annotations

import os
from pathlib import Path

import platformdirs

APP_NAME = "AutoZoopla"


def _ensure_home() -> None:
    """Repair a missing or degenerate ``$HOME`` before resolving paths.

    A GUI app launched from Finder/launchd can inherit an empty or ``/`` value
    for ``$HOME``. platformdirs (like ``os.path.expanduser``) trusts ``$HOME``,
    so that would place the app-data dir under the root-owned system location
    and make the database read-only. Fall back to the passwd database to get the
    real per-user home.
    """

    if os.name == "nt":
        return
    home = os.environ.get("HOME")
    if home and home != "/":
        return
    try:
        import pwd

        os.environ["HOME"] = pwd.getpwuid(os.getuid()).pw_dir
    except Exception:
        pass


def data_dir() -> Path:
    """Return (creating if needed) the per-user app-data directory.

    Uses platformdirs for the OS-correct location; Qt-free so the CLI and
    browser session can use it without a running ``QApplication``.
    """

    _ensure_home()
    path = Path(platformdirs.user_data_dir(APP_NAME, appauthor=False))
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
