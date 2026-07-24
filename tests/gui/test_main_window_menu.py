import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    # Redirect the app-data dir so the DB / credential store use a temp folder.
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    from relister.gui.main_window import MainWindow

    win = MainWindow()
    yield win
    win.close()
    win.deleteLater()
    qapp.processEvents()


def test_has_check_for_updates_action(window):
    assert hasattr(window, "check_updates_action")
    assert window.check_updates_action.text() == "Check for Updates…"


def test_window_title_shows_version(window):
    from relister.__version__ import __version__

    assert __version__ in window.windowTitle()


def test_sidebar_has_update_button_and_version(window):
    from relister.__version__ import __version__

    assert window.check_updates_button.text() == "Check for updates"
    assert __version__ in window.version_label.text()


def test_updater_reflects_platform(window):
    assert window._updater.available is (sys.platform == "darwin")


def test_check_for_updates_is_safe_off_macos(window, monkeypatch):
    # Off macOS the action shows an info dialog instead of invoking Sparkle;
    # patch the dialog so the test stays headless and asserts it is reached.
    calls = []
    monkeypatch.setattr(
        "relister.gui.main_window.QMessageBox.information",
        lambda *a, **k: calls.append(a),
    )
    window._check_for_updates()
    if sys.platform != "darwin":
        assert calls, "expected an info dialog off macOS"
