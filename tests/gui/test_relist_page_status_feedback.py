import logging
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from relister.gui.pages.relist_page import RelistPage
from relister.gui.prompt_bridge import PromptBridge
from relister.gui.services.settings_service import SettingsService


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def page(qapp):
    settings = SettingsService(QSettings("RelisterTest", f"unit-{os.getpid()}"))
    result = RelistPage(settings, PromptBridge(), logging.NullHandler())
    result.resize(1000, 800)
    result.images_edit.clear()
    result._validate_images_directory()
    result.show()
    qapp.processEvents()
    yield result
    result.close()
    result.deleteLater()
    qapp.processEvents()


def test_image_status_is_inline_and_hidden_for_neutral_state(page):
    assert page.image_status_label.isHidden()

    page._set_image_status("success", "Image folder ready")

    assert page.image_status_label.isVisible()
    assert page.image_status_label.text() == "Image folder ready"
    assert page.image_status_label.property("state") == "success"

    page._set_image_status("neutral", "ignored")

    assert page.image_status_label.isHidden()


def test_image_status_preserves_warning_and_error_states(page):
    page._set_image_status("warning", "Order needs attention")

    assert page.image_status_label.property("state") == "warning"
    assert page.top_banner.isHidden()

    page._set_image_status("error", "Folder cannot be read")

    assert page.image_status_label.property("state") == "error"
    assert page.top_banner.isHidden()


def test_workflow_banner_is_overlayed_and_closable(page):
    page.top_banner.show_banner("success", "Relist completed")
    page.top_banner._anim.stop()
    page.top_banner._finish_animation()

    assert page.top_banner.isVisible()
    assert page.top_banner.parentWidget() is page
    assert page.top_banner.property("state") == "success"
    assert page.top_banner.label.text() == "Relist completed"
    assert page.top_banner.geometry().top() == 0
    assert page.top_banner.geometry().width() == page.width()
    assert page.top_banner.close_button.text() == "×"

    page.top_banner.close_button.click()
    page.top_banner._anim.stop()
    page.top_banner._finish_animation()

    assert page.top_banner.isHidden()
