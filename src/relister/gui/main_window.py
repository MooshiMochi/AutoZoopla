from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import (
    QEvent,
    QEasingCurve,
    QPropertyAnimation,
    QSettings,
    QRect,
    Qt,
    QThread,
    QTimer,
)
from PySide6.QtGui import QCloseEvent, QColor, QStandardItemModel
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from image_manager.image_manager_app import (
    INSTRUCTIONS_FILENAME,
    ImageOrderPage,
    is_supported_image,
    load_images,
)

from .logging_handler import LogEmitter, QtLogHandler
from .prompt_bridge import PromptBridge
from .relist_worker import RelistRequest, RelistWorker
from .theme import ChevronCombo, ModernCheckBox, build_stylesheet

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderOption:
    label: str
    key: str
    enabled: bool = True


PROVIDERS = (
    ProviderOption("Zoopla", "zoopla"),
    ProviderOption("OnTheMarket (coming soon)", "onthemarket", False),
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AutoZoopla")
        self.resize(1220, 820)
        # Sized so the whole page - including the console and the input section -
        # is visible without scrolling. Minimum width is a touch wider than the
        # content needs; minimum height fits the full layout.
        self.setMinimumSize(1050, 770)

        self._settings = QSettings("Relister", "RelisterDesktop")
        self._thread: QThread | None = None
        self._worker: RelistWorker | None = None
        self._close_when_finished = False
        self._running = False
        self._images_ready = True
        self._organizer_return_to_relist = False

        self._prompt_bridge = PromptBridge()
        self._prompt_bridge.prompt_requested.connect(self._show_prompt)
        self._prompt_bridge.prompt_finished.connect(self._clear_prompt)

        self._log_emitter = LogEmitter()
        self._log_emitter.message_emitted.connect(self._append_log)
        self._log_handler = QtLogHandler(self._log_emitter)
        self._log_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logging.getLogger().addHandler(self._log_handler)

        self._images_validation_timer = QTimer(self)
        self._images_validation_timer.setSingleShot(True)
        self._images_validation_timer.setInterval(250)
        self._images_validation_timer.timeout.connect(self._validate_images_directory)

        self._build_ui()
        self._restore_settings()
        self._validate_images_directory()
        self._set_running(False)

    def _build_ui(self) -> None:
        shell = QFrame(self)
        shell.setObjectName("appRoot")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self.setCentralWidget(shell)

        sidebar = self._build_sidebar()
        shell_layout.addWidget(sidebar)

        self.pages = QStackedWidget()
        self.pages.setObjectName("pageStack")
        shell_layout.addWidget(self.pages, 1)

        self.relist_page = self._build_relist_page()
        self.image_page = ImageOrderPage()
        self.image_page.instructions_saved.connect(self._on_image_instructions_saved)
        self.image_page.directory_changed.connect(self._on_organizer_directory_changed)

        self.pages.addWidget(self.relist_page)
        self.pages.addWidget(self.image_page)
        self._switch_page(0)

        self._apply_styles()

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

        self.nav_relist = QPushButton("Relist property")
        self.nav_relist.setObjectName("navButton")
        self.nav_relist.setCheckable(True)
        self.nav_relist.clicked.connect(self._open_relist_from_navigation)

        self.nav_images = QPushButton("Image organiser")
        self.nav_images.setObjectName("navButton")
        self.nav_images.setCheckable(True)
        self.nav_images.clicked.connect(self._open_organizer_from_navigation)

        self.nav_group.addButton(self.nav_relist, 0)
        self.nav_group.addButton(self.nav_images, 1)
        layout.addWidget(self.nav_relist)
        layout.addWidget(self.nav_images)
        layout.addStretch(1)

        self.sidebar_hint = QLabel(
            "Prepare image order first, then run the relisting workflow from one place."
        )
        self.sidebar_hint.setObjectName("sidebarHint")
        self.sidebar_hint.setWordWrap(True)
        layout.addWidget(self.sidebar_hint)

        return sidebar

    def _build_relist_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("relistPage")
        self.relist_page = page
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        # The scroll area is a safety net; at the default and minimum window
        # sizes the whole page - console and input section included - fits
        # without scrolling.
        self.relist_scroll = QScrollArea()
        self.relist_scroll.setWidgetResizable(True)
        self.relist_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.relist_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        page_layout.addWidget(self.relist_scroll, 1)
        page.installEventFilter(self)
        self._build_top_banner(page)

        body = QWidget()
        body.setObjectName("relistBody")
        root = QVBoxLayout(body)
        root.setContentsMargins(20, 14, 20, 14)
        root.setSpacing(9)
        self.relist_scroll.setWidget(body)

        # Header: description and status badge. There is no oversized page
        # title - the sidebar already names the active section.
        header = QHBoxLayout()
        self.page_subtitle = QLabel(
            "Scrape an existing advert, prepare its images and recreate the listing."
        )
        self.page_subtitle.setObjectName("pageSubtitle")
        self.page_subtitle.setWordWrap(True)

        self.run_badge = QLabel("READY")
        self.run_badge.setObjectName("runBadge")
        self.run_badge.setProperty("state", "ready")
        self.run_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header.addWidget(self.page_subtitle, 1)
        header.addWidget(self.run_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(header)

        # Configuration card ----------------------------------------------
        configuration_card = QFrame()
        configuration_card.setObjectName("card")
        configuration_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        configuration_layout = QVBoxLayout(configuration_card)
        configuration_layout.setContentsMargins(16, 12, 16, 12)
        configuration_layout.setSpacing(10)

        # Providers - two columns, section tag inline with the field labels.
        self.source_combo = self._create_provider_combo()
        self.destination_combo = self._create_provider_combo()
        providers_grid = QGridLayout()
        providers_grid.setHorizontalSpacing(14)
        providers_grid.setVerticalSpacing(4)
        providers_grid.addWidget(self._field_label("Source provider"), 0, 0)
        providers_grid.addWidget(self._field_label("Destination provider"), 0, 1)
        providers_grid.addWidget(self.source_combo, 1, 0)
        providers_grid.addWidget(self.destination_combo, 1, 1)
        providers_grid.setColumnStretch(0, 1)
        providers_grid.setColumnStretch(1, 1)
        configuration_layout.addLayout(self._section_row("PROVIDERS", providers_grid))

        # Listing
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://pro.zoopla.co.uk/properties/listing/..."
        )
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.textChanged.connect(self._update_start_state)
        listing_content = QVBoxLayout()
        listing_content.setContentsMargins(0, 0, 0, 0)
        listing_content.setSpacing(4)
        listing_content.addWidget(self._field_label("Original listing URL"))
        listing_content.addWidget(self.url_edit)
        configuration_layout.addLayout(self._section_row("LISTING", listing_content))

        # Images
        self.images_edit = QLineEdit()
        self.images_edit.setPlaceholderText("Select a folder containing listing images")
        self.images_edit.setClearButtonEnabled(True)
        self.images_edit.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.images_edit.textChanged.connect(self._schedule_images_validation)

        self.browse_button = QPushButton("Browse")
        self.browse_button.clicked.connect(self._browse_images_directory)
        self.organize_button = QPushButton("Organise")
        self.organize_button.setObjectName("secondaryAccentButton")
        self.organize_button.clicked.connect(self._open_selected_images_in_organizer)

        images_row = QHBoxLayout()
        images_row.setContentsMargins(0, 0, 0, 0)
        images_row.setSpacing(8)
        images_row.addWidget(self.images_edit, 1)
        images_row.addWidget(self.browse_button)
        images_row.addWidget(self.organize_button)

        images_content = QVBoxLayout()
        images_content.setContentsMargins(0, 0, 0, 0)
        images_content.setSpacing(4)
        image_label_row = QHBoxLayout()
        image_label_row.setContentsMargins(0, 0, 0, 0)
        image_label_row.setSpacing(8)
        image_label_row.addWidget(
            self._field_label("Replacement image folder (optional)")
        )
        image_label_row.addStretch(1)
        self.image_status_label = QLabel()
        self.image_status_label.setObjectName("imageStatusLabel")
        self.image_status_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.image_status_label.setVisible(False)
        image_label_row.addWidget(self.image_status_label)
        images_content.addLayout(image_label_row)
        images_content.addLayout(images_row)
        configuration_layout.addLayout(self._section_row("IMAGES", images_content))

        # Options - deliberately unlabelled, aligned under the field column.
        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setSpacing(18)
        self.publish_checkbox = ModernCheckBox("Publish listing")
        self.publish_checkbox.setToolTip(
            "When unticked, the workflow runs in dry-run mode."
        )
        self.headless_checkbox = ModernCheckBox("Run browser headlessly")
        self.verbose_checkbox = ModernCheckBox("Verbose logs")
        self.verbose_checkbox.setChecked(True)
        options_row.addWidget(self.publish_checkbox)
        options_row.addWidget(self.headless_checkbox)
        options_row.addWidget(self.verbose_checkbox)
        options_row.addStretch(1)
        configuration_layout.addLayout(self._section_row("", options_row))

        root.addWidget(configuration_card)

        # Action bar -------------------------------------------------------
        action_bar = QFrame()
        action_bar.setObjectName("actionBar")
        action_bar.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        actions = QHBoxLayout(action_bar)
        actions.setContentsMargins(14, 8, 14, 8)
        actions.setSpacing(10)

        self.start_button = QPushButton("Start relist")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._start_relist)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("dangerButton")
        self.cancel_button.clicked.connect(self._cancel_relist)

        self.clear_logs_button = QPushButton("Clear output")
        self.clear_logs_button.clicked.connect(self.output_clear)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumWidth(150)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("workflowStatus")
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        actions.addWidget(self.start_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.clear_logs_button)
        actions.addSpacing(6)
        actions.addWidget(self.progress_bar)
        actions.addWidget(self.status_label, 1)
        root.addWidget(action_bar)

        # Program output ---------------------------------------------------
        output_card = QFrame()
        output_card.setObjectName("card")
        output_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding
        )
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(16, 10, 16, 12)
        output_layout.setSpacing(7)

        output_header = QHBoxLayout()
        output_title = QLabel("Program output")
        output_title.setObjectName("cardTitle")
        self.output_hint = QLabel("Live workflow and browser automation logs")
        self.output_hint.setObjectName("cardSubtitle")
        output_header.addWidget(output_title)
        output_header.addStretch(1)
        output_header.addWidget(self.output_hint)
        output_layout.addLayout(output_header)

        self.output_edit = QPlainTextEdit()
        self.output_edit.setObjectName("logOutput")
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText(
            "Workflow logs and progress messages will appear here."
        )
        self.output_edit.document().setMaximumBlockCount(5_000)
        self.output_edit.setMinimumHeight(120)
        output_layout.addWidget(self.output_edit)
        root.addWidget(output_card, 1)

        # User input section - always visible below the output, disabled until
        # the workflow asks for input.
        root.addWidget(self._build_input_section())

        return page

    def _build_top_banner(self, page: QWidget) -> QFrame:
        self.top_banner = QFrame(page)
        self.top_banner.setObjectName("topBanner")
        self.top_banner.setProperty("state", "success")
        self.top_banner.setGeometry(0, 0, page.width(), 0)
        self.top_banner.setVisible(False)

        layout = QHBoxLayout(self.top_banner)
        layout.setContentsMargins(20, 9, 18, 9)
        layout.setSpacing(10)

        self.top_banner_icon = QLabel("!")
        self.top_banner_icon.setObjectName("topBannerIcon")
        self.top_banner_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.top_banner_icon.setFixedSize(24, 24)

        self.top_banner_label = QLabel("")
        self.top_banner_label.setObjectName("topBannerText")
        self.top_banner_label.setWordWrap(True)

        self.top_banner_close = QPushButton("×")
        self.top_banner_close.setObjectName("topBannerClose")
        self.top_banner_close.setAccessibleName("Close status banner")
        self.top_banner_close.setToolTip("Close status banner")
        self.top_banner_close.setFixedSize(30, 30)
        self.top_banner_close.clicked.connect(self._hide_top_banner)

        layout.addWidget(self.top_banner_icon)
        layout.addWidget(self.top_banner_label, 1)
        layout.addWidget(self.top_banner_close)

        self._banner_anim = QPropertyAnimation(self.top_banner, b"geometry", self)
        self._banner_anim.setDuration(200)
        self._banner_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._banner_anim.finished.connect(self._finish_banner_animation)
        self._banner_hiding = False
        return self.top_banner

    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:
        if (
            watched is getattr(self, "relist_page", None)
            and event.type() == QEvent.Type.Resize
        ):
            self._position_top_banner()
        return super().eventFilter(watched, event)

    def _position_top_banner(self) -> None:
        if not hasattr(self, "top_banner"):
            return
        self.top_banner.setGeometry(
            0,
            0,
            self.relist_page.width(),
            self.top_banner.height(),
        )
        self.top_banner.raise_()

    def _build_input_section(self) -> QFrame:
        self.prompt_card = QFrame()
        self.prompt_card.setObjectName("promptCard")
        self.prompt_card.setProperty("active", False)
        self.prompt_card.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        layout = QVBoxLayout(self.prompt_card)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.prompt_title = QLabel("User input")
        self.prompt_title.setObjectName("promptTitle")
        self.prompt_badge = QLabel("NO INPUT NEEDED")
        self.prompt_badge.setObjectName("promptBadge")
        header.addWidget(self.prompt_title)
        header.addStretch(1)
        header.addWidget(self.prompt_badge)
        layout.addLayout(header)

        self.prompt_label = QLabel(
            "This box stays disabled until the workflow needs a login code or an "
            "answer to continue."
        )
        self.prompt_label.setObjectName("promptMessage")
        self.prompt_label.setWordWrap(True)
        layout.addWidget(self.prompt_label)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setObjectName("promptInput")
        self.prompt_edit.setProperty("active", False)
        self.prompt_edit.setPlaceholderText("Enter the requested value")
        self.prompt_edit.setEnabled(False)
        self.prompt_edit.returnPressed.connect(self._submit_prompt)
        self.submit_prompt_button = QPushButton("Submit response")
        self.submit_prompt_button.setObjectName("attentionButton")
        self.submit_prompt_button.setEnabled(False)
        self.submit_prompt_button.clicked.connect(self._submit_prompt)
        row.addWidget(self.prompt_edit, 1)
        row.addWidget(self.submit_prompt_button)
        layout.addLayout(row)

        # An accent-coloured glow on the input box while input is requested.
        self._prompt_glow = QGraphicsDropShadowEffect(self.prompt_edit)
        self._prompt_glow.setBlurRadius(16)
        self._prompt_glow.setOffset(0, 0)
        self._prompt_glow.setColor(QColor(79, 70, 229, 190))
        self._prompt_glow.setEnabled(False)
        self.prompt_edit.setGraphicsEffect(self._prompt_glow)

        return self.prompt_card

    def _section_row(self, tag_text: str, content_layout) -> QHBoxLayout:
        """A form section: a small-caps tag inline (left) with its field(s)."""

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(12)
        tag = QLabel(tag_text)
        tag.setObjectName("groupLabel")
        tag.setFixedWidth(72)
        row.addWidget(tag, 0, Qt.AlignmentFlag.AlignTop)
        row.addLayout(content_layout, 1)
        return row

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _create_provider_combo(self) -> QComboBox:
        combo = ChevronCombo()
        for option in PROVIDERS:
            combo.addItem(option.label, option.key)
            if not option.enabled:
                model = combo.model()
                if isinstance(model, QStandardItemModel):
                    item = model.item(combo.count() - 1)
                    if item is not None:
                        item.setEnabled(False)
        return combo

    def _apply_styles(self) -> None:
        self.setStyleSheet(build_stylesheet())

    def _restore_settings(self) -> None:
        geometry = self._settings.value("window_geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

        self._restore_combo_value(
            self.source_combo,
            str(self._settings.value("source", "zoopla")),
        )
        self._restore_combo_value(
            self.destination_combo,
            str(self._settings.value("destination", "zoopla")),
        )
        self.url_edit.setText(str(self._settings.value("listing_url", "")))
        self.images_edit.setText(str(self._settings.value("images_directory", "")))
        self.publish_checkbox.setChecked(
            self._as_bool(self._settings.value("publish", False))
        )
        self.headless_checkbox.setChecked(
            self._as_bool(self._settings.value("headless", False))
        )
        self.verbose_checkbox.setChecked(
            self._as_bool(self._settings.value("verbose", True))
        )

    @staticmethod
    def _restore_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in {"1", "true", "yes"}

    def _save_settings(self) -> None:
        self._settings.setValue("window_geometry", self.saveGeometry())
        self._settings.setValue("source", self.source_combo.currentData())
        self._settings.setValue("destination", self.destination_combo.currentData())
        self._settings.setValue("listing_url", self.url_edit.text().strip())
        self._settings.setValue("images_directory", self.images_edit.text().strip())
        self._settings.setValue("publish", self.publish_checkbox.isChecked())
        self._settings.setValue("headless", self.headless_checkbox.isChecked())
        self._settings.setValue("verbose", self.verbose_checkbox.isChecked())

    def _switch_page(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        button = self.nav_group.button(index)
        if button is not None:
            button.setChecked(True)

    def _open_relist_from_navigation(self, *_: object) -> None:
        self._organizer_return_to_relist = False
        self._switch_page(0)

    def _open_organizer_from_navigation(self, *_: object) -> None:
        self._organizer_return_to_relist = False
        images_text = self.images_edit.text().strip()
        if images_text and Path(images_text).is_dir():
            self.image_page.load_directory(Path(images_text))
        self._switch_page(1)

    def _open_selected_images_in_organizer(self) -> None:
        images_text = self.images_edit.text().strip()
        if not images_text:
            self._organizer_return_to_relist = True
            self._switch_page(1)
            self.image_page.choose_directory()
            return

        images_path = Path(images_text)
        if not images_path.is_dir():
            self._validation_error(
                f"The images path is not a directory:\n{images_path}"
            )
            return

        self._organizer_return_to_relist = True
        self.image_page.load_directory(images_path)
        self._switch_page(1)

    def _on_organizer_directory_changed(self, directory: str) -> None:
        if self._organizer_return_to_relist:
            self.status_label.setText(f"Organising images in {directory}")

    def _on_image_instructions_saved(self, directory: str) -> None:
        self.images_edit.setText(directory)
        self._validate_images_directory()
        self.status_label.setText("Image order saved. The relist is ready to continue.")

        if self._organizer_return_to_relist:
            self._organizer_return_to_relist = False
            self._switch_page(0)
            self.url_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def _schedule_images_validation(self, *_: object) -> None:
        self._images_validation_timer.start()
        self._update_start_state()

    def _browse_images_directory(self) -> None:
        initial = self.images_edit.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select listing images directory",
            initial,
        )
        if not selected:
            return

        self.images_edit.setText(selected)
        ready = self._validate_images_directory()
        if not ready:
            self._offer_image_directory_resolution(Path(selected))

    def _offer_image_directory_resolution(self, images_path: Path) -> None:
        if not images_path.is_dir():
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Image order required")
        box.setText("This image folder is not ready for relisting.")
        box.setInformativeText(
            f"{INSTRUCTIONS_FILENAME} is missing, empty or invalid. Open the image "
            "organiser to choose the visible images and save their order, or select "
            "a different folder."
        )
        organise = box.addButton(
            "Open image organiser",
            QMessageBox.ButtonRole.AcceptRole,
        )
        choose_another = box.addButton(
            "Choose another folder",
            QMessageBox.ButtonRole.ActionRole,
        )
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()

        if box.clickedButton() is organise:
            self._open_selected_images_in_organizer()
        elif box.clickedButton() is choose_another:
            QTimer.singleShot(0, self._browse_images_directory)

    def _validate_images_directory(self) -> bool:
        images_text = self.images_edit.text().strip()
        if not images_text:
            self._images_ready = True
            self._set_image_status(
                "neutral",
                "No replacement image folder selected. Existing scraped images will be used.",
                action_visible=False,
            )
            self._update_start_state()
            return True

        images_path = Path(images_text)
        if not images_path.is_dir():
            self._images_ready = False
            self._set_image_status(
                "error",
                "The selected image folder does not exist. Choose a different folder.",
                action_visible=False,
            )
            self._update_start_state()
            return False

        try:
            images = load_images(images_path)
        except OSError as exc:
            self._images_ready = False
            self._set_image_status(
                "error",
                f"The selected image folder could not be read: {exc}",
                action_visible=False,
            )
            self._update_start_state()
            return False

        if not images:
            self._images_ready = False
            self._set_image_status(
                "warning",
                "No supported images were found in this folder. Select a different folder.",
                action_visible=False,
            )
            self._update_start_state()
            return False

        instructions_path = images_path / INSTRUCTIONS_FILENAME
        if not instructions_path.is_file():
            self._images_ready = False
            self._set_image_status(
                "warning",
                f"{INSTRUCTIONS_FILENAME} is missing. Run the image organiser before continuing.",
                action_visible=True,
            )
            self._update_start_state()
            return False

        try:
            ordered_names = [
                line.strip()
                for line in instructions_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except OSError as exc:
            self._images_ready = False
            self._set_image_status(
                "error",
                f"{INSTRUCTIONS_FILENAME} could not be read: {exc}",
                action_visible=True,
            )
            self._update_start_state()
            return False

        if not ordered_names:
            self._images_ready = False
            self._set_image_status(
                "warning",
                f"{INSTRUCTIONS_FILENAME} is empty. Open the image organiser and save at least one visible image.",
                action_visible=True,
            )
            self._update_start_state()
            return False

        missing = [
            name for name in ordered_names if not is_supported_image(images_path / name)
        ]
        if missing:
            self._images_ready = False
            preview = ", ".join(missing[:3])
            suffix = "…" if len(missing) > 3 else ""
            self._set_image_status(
                "warning",
                f"The saved order refers to missing or unsupported files: {preview}{suffix}. Re-save the image order.",
                action_visible=True,
            )
            self._update_start_state()
            return False

        self._images_ready = True
        self._set_image_status(
            "success",
            f"Image folder ready: {len(ordered_names)} image{'s' if len(ordered_names) != 1 else ''} will be uploaded in the saved order.",
            action_visible=False,
        )
        self._update_start_state()
        return True

    def _set_image_status(
        self,
        state: str,
        message: str,
        *,
        action_visible: bool,
    ) -> None:
        del action_visible
        if state == "neutral":
            self.image_status_label.setVisible(False)
            return

        self.image_status_label.setText(message)
        self._set_dynamic_property(self.image_status_label, "state", state)
        self.image_status_label.setVisible(True)

    def _show_top_banner(self, state: str, message: str) -> None:
        self.top_banner_label.setText(message)
        self.top_banner_icon.setText("✓" if state == "success" else "!")
        self._set_dynamic_property(self.top_banner, "state", state)

        width = self.relist_page.width()
        target_height = self.top_banner.sizeHint().height()
        start_height = self.top_banner.height() if self.top_banner.isVisible() else 0
        start = QRect(0, 0, width, start_height)
        end = QRect(0, 0, width, target_height)
        self._banner_anim.stop()
        self._banner_hiding = False
        self.top_banner.setGeometry(start)
        self.top_banner.setVisible(True)
        self.top_banner.raise_()
        self._banner_anim.setStartValue(start)
        self._banner_anim.setEndValue(end)
        self._banner_anim.start()

    def _hide_top_banner(self) -> None:
        if self.top_banner.isHidden() and self.top_banner.height() == 0:
            return
        width = self.relist_page.width()
        start = self.top_banner.geometry()
        end = QRect(0, 0, width, 0)
        self._banner_anim.stop()
        self._banner_hiding = True
        self._banner_anim.setStartValue(start)
        self._banner_anim.setEndValue(end)
        self._banner_anim.start()

    def _finish_banner_animation(self) -> None:
        if self._banner_hiding:
            self.top_banner.setGeometry(0, 0, self.relist_page.width(), 0)
            self.top_banner.setVisible(False)
            self._banner_hiding = False
        else:
            self.top_banner.setVisible(True)
            self._position_top_banner()

    def _build_request(self) -> RelistRequest | None:
        listing_url = self.url_edit.text().strip()
        if not listing_url:
            self._validation_error("Enter the original listing URL.")
            self.url_edit.setFocus(Qt.FocusReason.OtherFocusReason)
            return None

        images_text = self.images_edit.text().strip()
        images_path = Path(images_text) if images_text else None
        if images_path is not None and not self._validate_images_directory():
            self._offer_image_directory_resolution(images_path)
            return None

        if self.publish_checkbox.isChecked():
            answer = QMessageBox.question(
                self,
                "Publish listing?",
                "This run will publish the recreated listing. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return None

        return RelistRequest(
            source=str(self.source_combo.currentData()),
            destination=str(self.destination_combo.currentData()),
            listing_url=listing_url,
            images_path=images_path,
            publish=self.publish_checkbox.isChecked(),
            headless=self.headless_checkbox.isChecked(),
        )

    def _validation_error(self, message: str) -> None:
        QMessageBox.warning(self, "Invalid configuration", message)

    def _start_relist(self) -> None:
        if self._thread is not None:
            return

        request = self._build_request()
        if request is None:
            return

        level = logging.DEBUG if self.verbose_checkbox.isChecked() else logging.INFO
        logging.getLogger().setLevel(level)
        self._log_handler.setLevel(level)

        self._save_settings()
        self._append_log("-" * 88)
        logger.info(
            "Starting %s -> %s relist for %s",
            request.source,
            request.destination,
            request.listing_url,
        )

        thread = QThread(self)
        worker = RelistWorker(request, self._prompt_bridge)
        worker.moveToThread(thread)

        thread.started.connect(worker.run)
        worker.status_changed.connect(self.status_label.setText)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self._on_failure)
        worker.cancelled.connect(self._on_cancelled)
        worker.done.connect(worker.deleteLater)
        worker.done.connect(thread.quit)
        worker.done.connect(self._on_worker_done)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        self._set_running(True)
        thread.start()

    def _cancel_relist(self) -> None:
        if self._worker is None:
            return
        self.status_label.setText("Cancelling…")
        self.cancel_button.setEnabled(False)
        self._worker.request_cancel()

    def _on_success(self, result: Any) -> None:
        listing = result.listing
        address = listing.address
        logger.info(
            "Property: %s, %s %s",
            address.street_name,
            address.town,
            address.postcode,
        )
        logger.info("Rent: £%s PCM", listing.rent_pcm)

        if result.published:
            logger.info(
                "Listing published successfully. Destination ID: %s",
                result.destination_listing_id,
            )
            if result.destination_listing_url:
                logger.info("New listing URL: %s", result.destination_listing_url)
            self.status_label.setText("Listing published successfully")
            self._show_top_banner("success", "Listing published successfully")
        else:
            logger.info("Dry run completed. No listing was published.")
            self.status_label.setText("Dry run completed")
            self._show_top_banner("success", "Dry run completed successfully")

    def _on_failure(self, error_message: str) -> None:
        self.status_label.setText("Relist failed")
        self._show_top_banner("error", f"Relist failed: {error_message}")
        QMessageBox.critical(
            self,
            "Relist failed",
            "The relist process failed.\n\n"
            f"{error_message}\n\n"
            "See Program output for the full log.",
        )

    def _on_cancelled(self) -> None:
        self.status_label.setText("Relist cancelled")

    def _on_worker_done(self) -> None:
        self._set_running(False)
        self._clear_prompt()

    def _on_thread_finished(self) -> None:
        self._thread = None
        self._worker = None
        if self._close_when_finished:
            self._close_when_finished = False
            self.close()

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.cancel_button.setEnabled(running)
        self.progress_bar.setVisible(running)

        self._set_dynamic_property(
            self.run_badge,
            "state",
            "running" if running else "ready",
        )
        self.run_badge.setText("RUNNING" if running else "READY")

        for widget in (
            self.source_combo,
            self.destination_combo,
            self.url_edit,
            self.images_edit,
            self.browse_button,
            self.organize_button,
            self.publish_checkbox,
            self.headless_checkbox,
            self.verbose_checkbox,
        ):
            widget.setEnabled(not running)

        if not running and not self._prompt_bridge.is_waiting:
            self.prompt_edit.setEnabled(False)
            self.submit_prompt_button.setEnabled(False)

        self._update_start_state()

    def _update_start_state(self, *_: object) -> None:
        if not hasattr(self, "start_button"):
            return

        has_url = bool(self.url_edit.text().strip())
        can_start = not self._running and has_url and self._images_ready
        self.start_button.setEnabled(can_start)

        if self._running:
            reason = "A relist operation is currently running."
        elif not has_url:
            reason = "Enter the original listing URL first."
        elif not self._images_ready:
            reason = "Prepare the selected image folder before continuing."
        else:
            reason = "Start the relisting workflow."
        self.start_button.setToolTip(reason)

    def _set_prompt_active(self, active: bool) -> None:
        """Toggle the accent glow + border on the always-present input box."""

        self._prompt_glow.setEnabled(active)
        self._set_dynamic_property(self.prompt_edit, "active", active)
        self._set_dynamic_property(self.prompt_card, "active", active)

    def _show_prompt(self, prompt: str, sensitive: bool) -> None:
        self._switch_page(0)
        self.prompt_title.setText("Action required")
        self.prompt_badge.setText("INPUT REQUIRED")
        self.prompt_label.setText(prompt)
        self.prompt_edit.clear()
        self.prompt_edit.setEchoMode(
            QLineEdit.EchoMode.Password if sensitive else QLineEdit.EchoMode.Normal
        )
        self.prompt_edit.setEnabled(True)
        self.submit_prompt_button.setEnabled(True)
        self._set_prompt_active(True)
        self.status_label.setText("Waiting for user input")
        self._set_dynamic_property(self.run_badge, "state", "attention")
        self.run_badge.setText("ACTION NEEDED")

        if self.isMinimized():
            self.showNormal()
        self.raise_()
        self.activateWindow()
        self.prompt_edit.setFocus(Qt.FocusReason.OtherFocusReason)

        app = QApplication.instance()
        if app is not None:
            app.alert(self, 0)
            app.beep()

    def _submit_prompt(self) -> None:
        if not self._prompt_bridge.is_waiting:
            return
        response = self.prompt_edit.text()
        self.prompt_edit.setEnabled(False)
        self.submit_prompt_button.setEnabled(False)
        self._set_prompt_active(False)
        self.prompt_badge.setText("SUBMITTED")
        self.prompt_label.setText("Response submitted. The workflow is continuing…")
        self._prompt_bridge.submit_response(response)
        self.status_label.setText("Continuing…")

    def _clear_prompt(self) -> None:
        self._set_prompt_active(False)

        self.prompt_title.setText("User input")
        self.prompt_badge.setText("NO INPUT NEEDED")
        self.prompt_label.setText(
            "This box stays disabled until the workflow needs a login code or an "
            "answer to continue."
        )
        self.prompt_edit.clear()
        self.prompt_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.prompt_edit.setEnabled(False)
        self.submit_prompt_button.setEnabled(False)

        self._set_dynamic_property(
            self.run_badge,
            "state",
            "running" if self._running else "ready",
        )
        self.run_badge.setText("RUNNING" if self._running else "READY")

    @staticmethod
    def _set_dynamic_property(widget: QWidget, name: str, value: Any) -> None:
        widget.setProperty(name, value)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def _append_log(self, message: str) -> None:
        self.output_edit.appendPlainText(message)
        scrollbar = self.output_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def output_clear(self) -> None:
        self.output_edit.clear()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_settings()

        if self._worker is None:
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
        self._cancel_relist()
        event.ignore()
