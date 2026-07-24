import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from relister.gui.pages.settings_page import SettingsPage
from relister.storage.app_settings import AppSettings
from relister.storage.credentials import CredentialStore


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _page(tmp_path):
    store = CredentialStore(tmp_path / "creds.enc")
    app_settings = AppSettings(tmp_path / "settings.json")
    return SettingsPage(store, app_settings), store, app_settings


def test_save_writes_credentials_and_branch(qapp, tmp_path):
    page, store, app_settings = _page(tmp_path)
    page.source_username.setText("src@example.com")
    page.source_password.setText("srcpass")
    page.destination_username.setText("dst@example.com")
    page.destination_password.setText("dstpass")
    page.branch_id_edit.setText("56042")

    page._save()

    assert store.get("zoopla", "source") == ("src@example.com", "srcpass")
    assert store.get("zoopla", "destination") == ("dst@example.com", "dstpass")
    assert app_settings.get("zoopla_branch_id") == "56042"


def test_reload_prefills_existing_values(qapp, tmp_path):
    _, store, app_settings = _page(tmp_path)
    store.set("zoopla", "source", "saved@example.com", "savedpass")
    app_settings.set("zoopla_branch_id", "777")

    page = SettingsPage(store, app_settings)

    assert page.source_username.text() == "saved@example.com"
    assert page.source_password.text() == "savedpass"
    assert page.branch_id_edit.text() == "777"


def test_save_shows_success_banner(qapp, tmp_path):
    page, _, _ = _page(tmp_path)
    page.resize(800, 600)
    page.show()
    qapp.processEvents()
    page.source_username.setText("u@e.com")
    page.source_password.setText("pw")

    page._save()
    page.top_banner._anim.stop()
    page.top_banner._finish_animation()

    assert page.top_banner.isVisible()
    assert page.top_banner.property("state") == "success"
    page.close()


def test_show_passwords_toggles_echo_mode(qapp, tmp_path):
    from PySide6.QtWidgets import QLineEdit

    page, _, _ = _page(tmp_path)
    assert page.source_password.echoMode() == QLineEdit.EchoMode.Password
    page.show_passwords.setChecked(True)
    assert page.source_password.echoMode() == QLineEdit.EchoMode.Normal
