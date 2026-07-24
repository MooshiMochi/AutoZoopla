from __future__ import annotations

import logging
import os
import sys


# Machine-wide browser cache written by the .pkg postinstall on macOS. Kept in
# sync with packaging/scripts/postinstall.
_MACOS_BROWSER_CACHE = "/Library/Application Support/AutoZoopla/ms-playwright"


def _pin_browser_cache_path() -> None:
    """Point Playwright at the bundled browser cache before it is imported.

    Only applies inside a frozen app bundle; in development the environment is
    left untouched so the developer's normal Playwright cache is used.
    """

    if os.environ.get("PLAYWRIGHT_BROWSERS_PATH"):
        return
    if not getattr(sys, "frozen", False):
        return
    if sys.platform == "darwin":
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _MACOS_BROWSER_CACHE


_pin_browser_cache_path()

from PySide6.QtWidgets import QApplication  # noqa: E402

# Absolute import: PyInstaller runs this file as __main__ (no package context),
# so a relative import would fail in the frozen app. Absolute works in both the
# frozen entry and the console-script (imported as relister.gui.app).
from relister.gui.main_window import MainWindow  # noqa: E402


def main() -> int:
    # Also send logs to stderr so startup errors are visible from a terminal /
    # crash log, not only in the in-app console. MainWindow additionally adds its
    # Qt console handler. basicConfig is a no-op if handlers already exist.
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(levelname)s %(name)s: %(message)s",
    )

    app = QApplication(sys.argv)
    app.setApplicationName("AutoZoopla")
    app.setOrganizationName("AutoZoopla")

    try:
        from relister.core.config import migrate_env_credentials

        migrate_env_credentials()
    except Exception:  # pragma: no cover - best-effort one-time migration
        pass

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
