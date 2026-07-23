import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from relister.gui.pages.relist_page import RelistPage
from relister.gui.prompt_bridge import PromptBridge
from relister.gui.services.settings_service import SettingsService
from relister.storage.property_images import PropertyImagesRepo


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _page(tmp_path, repo=None):
    settings = SettingsService(QSettings("RelisterTest", f"unit-{os.getpid()}"))
    settings.set_value("listing_url", "")
    settings.set_value("images_directory", "")
    return RelistPage(
        settings,
        PromptBridge(),
        logging.NullHandler(),
        repo=repo,
    )


def test_url_prefills_saved_images_folder(qapp, tmp_path):
    repo = PropertyImagesRepo(tmp_path / "db.sqlite")
    repo.set_images_dir("5356300", str(tmp_path / "imgs"))
    page = _page(tmp_path, repo=repo)

    page.url_edit.setText("https://pro.zoopla.co.uk/properties/listing/5356300")

    assert page.images_edit.text() == str(tmp_path / "imgs")


def test_prefill_does_not_clobber_manual_folder(qapp, tmp_path):
    repo = PropertyImagesRepo(tmp_path / "db.sqlite")
    repo.set_images_dir("5356300", str(tmp_path / "saved"))
    page = _page(tmp_path, repo=repo)
    page.images_edit.setText(str(tmp_path / "manual"))

    page.url_edit.setText("https://pro.zoopla.co.uk/properties/listing/5356300")

    assert page.images_edit.text() == str(tmp_path / "manual")


def test_unknown_listing_leaves_images_empty(qapp, tmp_path):
    repo = PropertyImagesRepo(tmp_path / "db.sqlite")
    page = _page(tmp_path, repo=repo)

    page.url_edit.setText("https://pro.zoopla.co.uk/properties/listing/999")

    assert page.images_edit.text() == ""
