import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from relister.gui.main_window import MainWindow


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    result = MainWindow()
    result.images_edit.clear()
    result._validate_images_directory()
    result.show()
    qapp.processEvents()
    yield result
    result.close()
    result.deleteLater()
    qapp.processEvents()


def test_image_status_is_inline_and_hidden_for_neutral_state(window):
    assert window.image_status_label.isHidden()

    window._set_image_status("success", "Image folder ready", action_visible=False)

    assert window.image_status_label.isVisible()
    assert window.image_status_label.text() == "Image folder ready"
    assert window.image_status_label.property("state") == "success"

    window._set_image_status("neutral", "ignored", action_visible=False)

    assert window.image_status_label.isHidden()


def test_image_status_preserves_warning_and_error_states(window):
    window._set_image_status("warning", "Order needs attention", action_visible=True)

    assert window.image_status_label.property("state") == "warning"
    assert window.top_banner.isHidden()

    window._set_image_status("error", "Folder cannot be read", action_visible=False)

    assert window.image_status_label.property("state") == "error"
    assert window.top_banner.isHidden()


def test_workflow_banner_is_overlayed_and_closable(window):
    window._show_top_banner("success", "Relist completed")
    window._banner_anim.stop()
    window._finish_banner_animation()

    assert window.top_banner.isVisible()
    assert window.top_banner.parentWidget() is window.relist_page
    assert window.top_banner.property("state") == "success"
    assert window.top_banner_label.text() == "Relist completed"
    assert window.top_banner.geometry().top() == 0
    assert window.top_banner.geometry().width() == window.relist_page.width()
    assert window.top_banner_close.text() == "×"

    window.top_banner_close.click()
    window._banner_anim.stop()
    window._finish_banner_animation()

    assert window.top_banner.isHidden()
