from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from image_manager.image_manager_app import INSTRUCTIONS_FILENAME

from ...providers.factory import provider_class_for
from ...storage.property_images import PropertyImagesRepo
from ..prompt_bridge import PromptBridge
from ..relist_worker import RelistRequest, RelistWorker
from ..services.images_validator import validate_images_directory
from ..services.settings_service import SettingsService
from ..theme import ChevronCombo, ModernCheckBox
from ..widgets.form_helpers import field_label, section_row
from ..widgets.prompt_panel import PromptPanel
from ..widgets.top_banner import TopBanner
from .base_page import BasePage

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


class RelistPage(BasePage):
    """The relisting workspace: form, validation, and worker lifecycle."""

    nav_label = "Relist property"

    # Ask the shell to open the image organiser (with an optional folder to load).
    request_organiser = Signal(object)  # Path | None
    # Ask the shell to bring this page forward (workflow needs attention).
    attention_requested = Signal()
    # Emitted once the worker thread has fully finished.
    finished = Signal()

    def __init__(
        self,
        settings: SettingsService,
        prompt_bridge: PromptBridge,
        log_handler: logging.Handler,
        repo: PropertyImagesRepo | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("relistPage")

        self._settings = settings
        self._prompt_bridge = prompt_bridge
        self._log_handler = log_handler
        self._repo = repo

        self._thread: QThread | None = None
        self._worker: RelistWorker | None = None
        self._active_request: RelistRequest | None = None
        self._running = False
        self._images_ready = True

        self._prompt_bridge.prompt_requested.connect(self._show_prompt)
        self._prompt_bridge.prompt_finished.connect(self._clear_prompt)

        self._images_validation_timer = QTimer(self)
        self._images_validation_timer.setSingleShot(True)
        self._images_validation_timer.setInterval(250)
        self._images_validation_timer.timeout.connect(self._validate_images_directory)

        self._build_ui()
        self.restore_settings()
        self._validate_images_directory()
        self._set_running(False)

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        self.relist_scroll = QScrollArea()
        self.relist_scroll.setWidgetResizable(True)
        self.relist_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.relist_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        page_layout.addWidget(self.relist_scroll, 1)

        self.top_banner = TopBanner(self)

        body = QWidget()
        body.setObjectName("relistBody")
        root = QVBoxLayout(body)
        root.setContentsMargins(20, 14, 20, 14)
        root.setSpacing(9)
        self.relist_scroll.setWidget(body)

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

        self.source_combo = self._create_provider_combo()
        self.destination_combo = self._create_provider_combo()
        providers_grid = QGridLayout()
        providers_grid.setHorizontalSpacing(14)
        providers_grid.setVerticalSpacing(4)
        providers_grid.addWidget(field_label("Source provider"), 0, 0)
        providers_grid.addWidget(field_label("Destination provider"), 0, 1)
        providers_grid.addWidget(self.source_combo, 1, 0)
        providers_grid.addWidget(self.destination_combo, 1, 1)
        providers_grid.setColumnStretch(0, 1)
        providers_grid.setColumnStretch(1, 1)
        configuration_layout.addLayout(section_row("PROVIDERS", providers_grid))
        self.source_combo.currentIndexChanged.connect(self._maybe_prefill_images)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://pro.zoopla.co.uk/properties/listing/..."
        )
        self.url_edit.setClearButtonEnabled(True)
        self.url_edit.textChanged.connect(self._update_start_state)
        self.url_edit.textChanged.connect(self._maybe_prefill_images)
        listing_content = QVBoxLayout()
        listing_content.setContentsMargins(0, 0, 0, 0)
        listing_content.setSpacing(4)
        listing_content.addWidget(field_label("Original listing URL"))
        listing_content.addWidget(self.url_edit)
        configuration_layout.addLayout(section_row("LISTING", listing_content))

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
        image_label_row.addWidget(field_label("Replacement image folder (optional)"))
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
        configuration_layout.addLayout(section_row("IMAGES", images_content))

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
        configuration_layout.addLayout(section_row("", options_row))

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

        # User-input panel (always present, disabled until needed).
        self.prompt_panel = PromptPanel()
        self.prompt_panel.submitted.connect(self._submit_prompt)
        root.addWidget(self.prompt_panel)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self.top_banner.reposition()

    # ------------------------------------------------------------- providers

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

    @staticmethod
    def _restore_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    # -------------------------------------------------------------- settings

    def restore_settings(self) -> None:
        self._restore_combo_value(
            self.source_combo, self._settings.value("source", "zoopla")
        )
        self._restore_combo_value(
            self.destination_combo, self._settings.value("destination", "zoopla")
        )
        self.url_edit.setText(self._settings.value("listing_url", ""))
        self.images_edit.setText(self._settings.value("images_directory", ""))
        self.publish_checkbox.setChecked(self._settings.bool_value("publish", False))
        self.headless_checkbox.setChecked(self._settings.bool_value("headless", False))
        self.verbose_checkbox.setChecked(self._settings.bool_value("verbose", True))

    def save_settings(self) -> None:
        self._settings.set_value("source", self.source_combo.currentData())
        self._settings.set_value("destination", self.destination_combo.currentData())
        self._settings.set_value("listing_url", self.url_edit.text().strip())
        self._settings.set_value("images_directory", self.images_edit.text().strip())
        self._settings.set_value("publish", self.publish_checkbox.isChecked())
        self._settings.set_value("headless", self.headless_checkbox.isChecked())
        self._settings.set_value("verbose", self.verbose_checkbox.isChecked())

    # ----------------------------------------------- shell coordination API

    def images_text(self) -> str:
        return self.images_edit.text().strip()

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def show_success_banner(self, message: str) -> None:
        self.top_banner.show_banner("success", message)

    def set_images_dir(self, directory: str) -> None:
        self.images_edit.setText(directory)
        self._validate_images_directory()
        self.status_label.setText(
            "Image order saved. The relist is ready to continue."
        )

    def has_active_worker(self) -> bool:
        return self._worker is not None

    def append_log(self, message: str) -> None:
        self.output_edit.appendPlainText(message)
        scrollbar = self.output_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def output_clear(self) -> None:
        self.output_edit.clear()

    # ------------------------------------------------------------- images UI

    def _schedule_images_validation(self, *_: object) -> None:
        self._images_validation_timer.start()
        self._update_start_state()

    def _browse_images_directory(self) -> None:
        initial = self.images_edit.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            self, "Select listing images directory", initial
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
            "Open image organiser", QMessageBox.ButtonRole.AcceptRole
        )
        choose_another = box.addButton(
            "Choose another folder", QMessageBox.ButtonRole.ActionRole
        )
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()

        if box.clickedButton() is organise:
            self._open_selected_images_in_organizer()
        elif box.clickedButton() is choose_another:
            QTimer.singleShot(0, self._browse_images_directory)

    def _open_selected_images_in_organizer(self) -> None:
        images_text = self.images_edit.text().strip()
        if not images_text:
            self.request_organiser.emit(None)
            return

        images_path = Path(images_text)
        if not images_path.is_dir():
            self._validation_error(
                f"The images path is not a directory:\n{images_path}"
            )
            return

        self.request_organiser.emit(images_path)

    def _validate_images_directory(self) -> bool:
        result = validate_images_directory(self.images_edit.text())
        self._images_ready = result.ready
        self._set_image_status(result.state, result.message)
        self._update_start_state()
        return result.ready

    def _set_image_status(self, state: str, message: str) -> None:
        if state == "neutral":
            self.image_status_label.setVisible(False)
            return
        self.image_status_label.setText(message)
        self._set_dynamic_property(self.image_status_label, "state", state)
        self.image_status_label.setVisible(True)

    # ------------------------------------------------------------ worker run

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

        self.save_settings()
        self._save_images_mapping(request)
        self._active_request = request
        self.append_log("-" * 88)
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

    def cancel(self) -> None:
        self._cancel_relist()

    def _cancel_relist(self) -> None:
        if self._worker is None:
            return
        self.status_label.setText("Cancelling…")
        self.cancel_button.setEnabled(False)
        self._worker.request_cancel()

    def _maybe_prefill_images(self, *_: object) -> None:
        if self._repo is None:
            return
        if self.images_edit.text().strip():
            return
        provider_class = provider_class_for(str(self.source_combo.currentData()))
        if provider_class is None:
            return
        listing_id = provider_class.extract_listing_id(self.url_edit.text().strip())
        if not listing_id:
            return
        saved = self._repo.get_images_dir(listing_id)
        if saved:
            self.images_edit.setText(saved)
            self.status_label.setText("Loaded saved image folder for this listing.")

    def _save_images_mapping(self, request: RelistRequest) -> None:
        if self._repo is None or request.images_path is None:
            return
        provider_class = provider_class_for(request.source)
        if provider_class is None:
            return
        listing_id = provider_class.extract_listing_id(request.listing_url)
        if listing_id:
            self._repo.set_images_dir(listing_id, str(request.images_path))

    def _migrate_images_mapping(self, result: Any) -> None:
        if self._repo is None or not result.published:
            return
        request = self._active_request
        if request is None:
            return
        source_class = provider_class_for(request.source)
        dest_class = provider_class_for(request.destination)
        if source_class is None or dest_class is None:
            return
        old_id = source_class.extract_listing_id(request.listing_url)
        new_id = result.destination_listing_id
        if not new_id and result.destination_listing_url:
            new_id = dest_class.extract_listing_id(result.destination_listing_url)
        if old_id and new_id:
            self._repo.migrate_id(old_id, new_id)

    def _on_success(self, result: Any) -> None:
        self._migrate_images_mapping(result)
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
            self.top_banner.show_banner("success", "Listing published successfully")
        else:
            logger.info("Dry run completed. No listing was published.")
            self.status_label.setText("Dry run completed")
            self.top_banner.show_banner("success", "Dry run completed successfully")

    def _on_failure(self, error_message: str) -> None:
        self.status_label.setText("Relist failed")
        self.top_banner.show_banner("error", f"Relist failed: {error_message}")
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
        self.finished.emit()

    def _set_running(self, running: bool) -> None:
        self._running = running
        self.cancel_button.setEnabled(running)
        self.progress_bar.setVisible(running)

        self._set_dynamic_property(
            self.run_badge, "state", "running" if running else "ready"
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
            self.prompt_panel.edit.setEnabled(False)
            self.prompt_panel.submit_button.setEnabled(False)

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

    # ---------------------------------------------------------------- prompt

    def _show_prompt(self, prompt: str, sensitive: bool) -> None:
        self.attention_requested.emit()
        self.prompt_panel.show_prompt(prompt, sensitive)
        self.status_label.setText("Waiting for user input")
        self._set_dynamic_property(self.run_badge, "state", "attention")
        self.run_badge.setText("ACTION NEEDED")

        window = self.window()
        if window is not None:
            if window.isMinimized():
                window.showNormal()
            window.raise_()
            window.activateWindow()
        self.prompt_panel.focus_input()

        app = QApplication.instance()
        if app is not None:
            if window is not None:
                app.alert(window, 0)
            app.beep()

    def _submit_prompt(self, response: str) -> None:
        if not self._prompt_bridge.is_waiting:
            return
        self.prompt_panel.mark_submitted()
        self._prompt_bridge.submit_response(response)
        self.status_label.setText("Continuing…")

    def _clear_prompt(self) -> None:
        self.prompt_panel.clear()
        self._set_dynamic_property(
            self.run_badge, "state", "running" if self._running else "ready"
        )
        self.run_badge.setText("RUNNING" if self._running else "READY")

    # ---------------------------------------------------------------- helper

    @staticmethod
    def _set_dynamic_property(widget: QWidget, name: str, value: Any) -> None:
        widget.setProperty(name, value)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()
