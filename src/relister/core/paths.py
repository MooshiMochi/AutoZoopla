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


def _permission_hint(path: Path) -> str:
    return (
        f"Cannot write to the app data folder:\n{path}\n\n"
        f"Fix its permissions with:\n"
        f'  sudo chown -R "$(whoami)" "{path}"'
    )


def _ensure_dir(directory: Path) -> Path:
    """Create ``directory`` (and parents) and confirm it is writable.

    Raises a :class:`PermissionError` with an actionable message rather than a
    deep, cryptic traceback when the folder exists but is not writable (e.g.
    left root-owned by an installer).
    """

    try:
        directory.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise PermissionError(_permission_hint(directory)) from exc
    if not os.access(directory, os.W_OK):
        raise PermissionError(_permission_hint(directory))
    return directory


def data_dir() -> Path:
    """Return the per-user app-data directory (best effort, never raises).

    Uses platformdirs for the OS-correct location; Qt-free so the CLI and
    browser session can use it without a running ``QApplication``. Writability
    is enforced at the actual write sites (see :func:`ensure_writable`), so that
    merely building a path never fails.
    """

    _ensure_home()
    path = Path(platformdirs.user_data_dir(APP_NAME, appauthor=False))
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass  # surfaced with a clear message when we actually write
    return path


def ensure_writable() -> Path:
    """Return the data dir, raising an actionable error if it is not writable."""

    return _ensure_dir(data_dir())


def database_path() -> Path:
    return data_dir() / "relister.db"


def credentials_path() -> Path:
    return data_dir() / "credentials.enc"


def browser_states_dir() -> Path:
    return _ensure_dir(data_dir() / "browser_states")


def browser_cache_dir() -> Path:
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    return Path(override) if override else data_dir() / "ms-playwright"
