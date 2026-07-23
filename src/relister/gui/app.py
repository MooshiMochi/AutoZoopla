from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main() -> int:
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
