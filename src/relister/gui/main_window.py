from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .logging_handler import LogEmitter, QtLogHandler
from .navigation import NavItem
from .pages.image_page import ImagePage
from .pages.relist_page import RelistPage
from .prompt_bridge import PromptBridge
from .services.settings_service import SettingsService
from .theme import build_stylesheet
from ..storage.credentials import CredentialStore
from ..storage.property_images import PropertyImagesRepo

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Thin application shell: a sidebar-driven stack of workspace pages."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AutoZoopla")
        self.resize(1220, 820)
        self.setMinimumSize(1050, 770)

        self._settings = SettingsService()
        self._prompt_bridge = PromptBridge()
        self._close_when_finished = False

        self._log_emitter = LogEmitter()
        self._log_handler = QtLogHandler(self._log_emitter)
        self._log_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logging.getLogger().addHandler(self._log_handler)

        # Pages ------------------------------------------------------------
        self._repo = PropertyImagesRepo()
        self._credentials = CredentialStore()
        self.relist_page = RelistPage(
            self._settings,
            self._prompt_bridge,
            self._log_handler,
            repo=self._repo,
            credentials=self._credentials,
        )
        self.image_page = ImagePage()
        self._organizer_return_to_relist = False

        self._nav_items = (
            NavItem("relist", self.relist_page.nav_label, lambda: self.relist_page),
            NavItem("images", self.image_page.nav_label, lambda: self.image_page),
        )

        self._build_ui()
        self._wire_pages()

        self._log_emitter.message_emitted.connect(self.relist_page.append_log)

        self._restore_geometry()
        self._switch_to_index(0)

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        shell = QFrame(self)
        shell.setObjectName("appRoot")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self.setCentralWidget(shell)

        shell_layout.addWidget(self._build_sidebar())

        self.pages = QStackedWidget()
        self.pages.setObjectName("pageStack")
        shell_layout.addWidget(self.pages, 1)

        for item in self._nav_items:
            self.pages.addWidget(item.factory())

        self.setStyleSheet(build_stylesheet())

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 22, 10, 18)
        layout.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)
        brand_mark = QLabel("AZ")
        brand_mark.setObjectName("brandMark")
        brand_mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_mark.setFixedSize(44, 44)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(1)
        brand_title = QLabel("AutoZoopla")
        brand_title.setObjectName("brandTitle")
        brand_subtitle = QLabel("Relister workspace")
        brand_subtitle.setObjectName("brandSubtitle")
        brand_text.addWidget(brand_title)
        brand_text.addWidget(brand_subtitle)

        brand_row.addWidget(brand_mark)
        brand_row.addLayout(brand_text, 1)
        layout.addLayout(brand_row)
        layout.addSpacing(26)

        section_label = QLabel("WORKSPACE")
        section_label.setObjectName("sidebarSection")
        layout.addWidget(section_label)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        for index, item in enumerate(self._nav_items):
            button = QPushButton(item.label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda _checked=False, i=index: self._on_nav_clicked(i)
            )
            self.nav_group.addButton(button, index)
            layout.addWidget(button)

        layout.addStretch(1)

        self.sidebar_hint = QLabel(
            "Prepare image order first, then run the relisting workflow from one place."
        )
        self.sidebar_hint.setObjectName("sidebarHint")
        self.sidebar_hint.setWordWrap(True)
        layout.addWidget(self.sidebar_hint)

        return sidebar

    def _wire_pages(self) -> None:
        self.relist_page.request_organiser.connect(self._open_organiser_from_relist)
        self.relist_page.attention_requested.connect(
            lambda: self._switch_to_index(0)
        )
        self.relist_page.finished.connect(self._on_relist_finished)
        self.image_page.instructions_saved.connect(self._on_image_instructions_saved)
        self.image_page.directory_changed.connect(
            self._on_organizer_directory_changed
        )

    # ------------------------------------------------------------ navigation

    def _switch_to_index(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        button = self.nav_group.button(index)
        if button is not None:
            button.setChecked(True)
        page = self.pages.widget(index)
        if hasattr(page, "on_activated"):
            page.on_activated()

    def _on_nav_clicked(self, index: int) -> None:
        self._organizer_return_to_relist = False
        if self._nav_items[index].key == "images":
            images_text = self.relist_page.images_text()
            from pathlib import Path

            if images_text and Path(images_text).is_dir():
                self.image_page.load_directory(Path(images_text))
        self._switch_to_index(index)

    # --------------------------------------------------- cross-page handlers

    def _open_organiser_from_relist(self, images_path: object) -> None:
        self._organizer_return_to_relist = True
        self._switch_to_index(1)
        if images_path is None:
            self.image_page.choose_directory()
        else:
            self.image_page.load_directory(images_path)

    def _on_organizer_directory_changed(self, directory: str) -> None:
        if self._organizer_return_to_relist:
            self.relist_page.set_status(f"Organising images in {directory}")

    def _on_image_instructions_saved(self, directory: str) -> None:
        self.relist_page.set_images_dir(directory)
        if self._organizer_return_to_relist:
            self._organizer_return_to_relist = False
            self._switch_to_index(0)
            self.relist_page.url_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    # ------------------------------------------------------------- lifecycle

    def _restore_geometry(self) -> None:
        geometry = self._settings.geometry()
        if geometry is not None:
            self.restoreGeometry(geometry)

    def _on_relist_finished(self) -> None:
        if self._close_when_finished:
            self._close_when_finished = False
            self.close()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt override)
        self._settings.set_geometry(self.saveGeometry())
        self.relist_page.save_settings()

        if not self.relist_page.has_active_worker():
            self.image_page.shutdown()
            logging.getLogger().removeHandler(self._log_handler)
            event.accept()
            return

        answer = QMessageBox.question(
            self,
            "Relist still running",
            "A relist operation is still running. Cancel it and close the application?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.No:
            event.ignore()
            return

        self._close_when_finished = True
        self.relist_page.cancel()
        event.ignore()
