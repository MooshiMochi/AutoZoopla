from __future__ import annotations

import logging
import os
import sys
import threading
import time

logger = logging.getLogger(__name__)


def _pin_browser_cache_path() -> None:
    """Point Playwright at the per-user browser cache before it is imported.

    Only applies inside a frozen app bundle; in development the environment is
    left untouched so the developer's normal Playwright cache is used.
    """

    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return
    if not getattr(sys, "frozen", False):
        return
    try:
        from relister.core import paths

        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(paths.data_dir() / "ms-playwright")
    except Exception:  # pragma: no cover - best effort
        pass


_pin_browser_cache_path()

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication, QProgressDialog  # noqa: E402

# Absolute import: PyInstaller runs this file as __main__ (no package context),
# so a relative import would fail in the frozen app. Absolute works in both the
# frozen entry and the console-script (imported as relister.gui.app).
from relister.gui.main_window import MainWindow  # noqa: E402


def _app_icon_path() -> str | None:
    """Locate the bundled app icon (PNG) in both frozen and dev layouts."""

    from pathlib import Path

    candidates = []
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None)
        if base:
            candidates.append(Path(base) / "icons" / "AutoZoopla.png")
    # Development: repo-root/packaging/icons.
    here = Path(__file__).resolve()
    candidates.append(here.parents[3] / "packaging" / "icons" / "AutoZoopla.png")

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _browsers_present() -> bool:
    from relister.core import paths

    cache = paths.browser_cache_dir()
    return any(cache.glob("firefox-*")) or any(cache.glob("webkit-*"))


def _install_browsers() -> int:
    """Download Firefox + WebKit via the bundled Playwright driver."""

    import subprocess

    from playwright._impl._driver import compute_driver_executable, get_driver_env

    executable = compute_driver_executable()
    args = list(executable) if isinstance(executable, (list, tuple)) else [executable]
    completed = subprocess.run(
        [*args, "install", "firefox", "webkit"],
        env={**os.environ, **get_driver_env()},
    )
    return completed.returncode


def _ensure_browsers(app: QApplication) -> None:
    """On first launch of the frozen app, download browsers if they're missing.

    Runs the download on a worker thread while showing an indeterminate progress
    dialog, so the one-time setup is visible and the UI stays responsive. In
    development this is skipped (the developer's own Playwright cache is used).
    """

    if not getattr(sys, "frozen", False):
        return
    if os.environ.get("AUTOZOOPLA_SKIP_BROWSER_SETUP"):
        return
    try:
        if _browsers_present():
            return
    except Exception:
        return

    dialog = QProgressDialog(
        "Setting up browser components.\nThis one-time download may take a few minutes…",
        None,
        0,
        0,
    )
    dialog.setWindowTitle("AutoZoopla setup")
    dialog.setCancelButton(None)
    dialog.setMinimumDuration(0)
    dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
    dialog.show()
    app.processEvents()

    outcome: dict = {}

    def _work() -> None:
        try:
            outcome["code"] = _install_browsers()
        except Exception as exc:  # pragma: no cover - runtime/network dependent
            outcome["error"] = exc

    worker = threading.Thread(target=_work, daemon=True)
    worker.start()
    while worker.is_alive():
        app.processEvents()
        time.sleep(0.05)
    dialog.close()

    if outcome.get("error") or outcome.get("code", 0) != 0:
        logger.error(
            "Browser setup did not complete: %s. Relisting will not work until "
            "browsers are installed.",
            outcome.get("error") or f"exit code {outcome.get('code')}",
        )


def main() -> int:
    # Also send logs to stderr so startup errors are visible from a terminal /
    # crash log, not only in the in-app console. MainWindow additionally adds its
    # Qt console handler. basicConfig is a no-op if handlers already exist.
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # Headless mode used by tooling to pre-download browsers (no GUI).
    if "--install-browsers" in sys.argv:
        return _install_browsers()

    app = QApplication(sys.argv)
    app.setApplicationName("AutoZoopla")
    app.setOrganizationName("AutoZoopla")

    icon_path = _app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    try:
        from relister.core.config import migrate_env_credentials

        migrate_env_credentials()
    except Exception:  # pragma: no cover - best-effort one-time migration
        pass

    _ensure_browsers(app)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
