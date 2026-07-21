from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings, Qt, QThread
from PySide6.QtGui import QCloseEvent, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .logging_handler import LogEmitter, QtLogHandler
from .prompt_bridge import PromptBridge
from .relist_worker import RelistRequest, RelistWorker

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProviderOption:
    label: str
    key: str
    enabled: bool = True


PROVIDERS = (
    ProviderOption("Zoopla", "zoopla"),
    ProviderOption("Expert OnTheMarket (coming soon)", "onthemarket", False),
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Relister")
        self.setMinimumSize(920, 700)

        self._settings = QSettings("Relister", "RelisterDesktop")
        self._thread: QThread | None = None
        self._worker: RelistWorker | None = None
        self._close_when_finished = False

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

        self._build_ui()
        self._restore_settings()
        self._set_running(False)

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)
        self.setCentralWidget(central)

        title = QLabel("Property Relister")
        title.setObjectName("titleLabel")
        subtitle = QLabel(
            "Scrape and recreate property listings without using the command line."
        )
        subtitle.setObjectName("subtitleLabel")
        root.addWidget(title)
        root.addWidget(subtitle)

        configuration_group = QGroupBox("Relist configuration")
        form = QFormLayout(configuration_group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)

        self.source_combo = self._create_provider_combo()
        self.destination_combo = self._create_provider_combo()

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText(
            "https://pro.zoopla.co.uk/properties/listing/..."
        )
        self.url_edit.setClearButtonEnabled(True)

        images_container = QWidget()
        images_row = QHBoxLayout(images_container)
        images_row.setContentsMargins(0, 0, 0, 0)
        images_row.setSpacing(8)

        self.images_edit = QLineEdit()
        self.images_edit.setPlaceholderText(
            "Folder containing images and instructions.txt"
        )
        self.images_edit.setClearButtonEnabled(True)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.clicked.connect(self._browse_images_directory)
        images_row.addWidget(self.images_edit, 1)
        images_row.addWidget(self.browse_button)

        options_container = QWidget()
        options_row = QHBoxLayout(options_container)
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setSpacing(24)

        self.publish_checkbox = QCheckBox("Publish listing")
        self.publish_checkbox.setToolTip(
            "When unticked, the workflow runs in dry-run mode."
        )
        self.headless_checkbox = QCheckBox("Run browser headlessly")
        self.verbose_checkbox = QCheckBox("Verbose logs")
        self.verbose_checkbox.setChecked(True)

        options_row.addWidget(self.publish_checkbox)
        options_row.addWidget(self.headless_checkbox)
        options_row.addWidget(self.verbose_checkbox)
        options_row.addStretch(1)

        form.addRow("Source provider", self.source_combo)
        form.addRow("Destination provider", self.destination_combo)
        form.addRow("Original listing URL", self.url_edit)
        form.addRow("Images directory", images_container)
        form.addRow("Options", options_container)
        root.addWidget(configuration_group)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        self.start_button = QPushButton("Start relist")
        self.start_button.setObjectName("primaryButton")
        self.start_button.clicked.connect(self._start_relist)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self._cancel_relist)

        self.clear_logs_button = QPushButton("Clear output")
        self.clear_logs_button.clicked.connect(self.output_clear)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setMaximumWidth(170)

        self.status_label = QLabel("Ready")
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        actions.addWidget(self.start_button)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.clear_logs_button)
        actions.addSpacing(8)
        actions.addWidget(self.progress_bar)
        actions.addWidget(self.status_label, 1)
        root.addLayout(actions)

        splitter = QSplitter(Qt.Orientation.Vertical)

        output_group = QGroupBox("Program output")
        output_layout = QVBoxLayout(output_group)
        self.output_edit = QPlainTextEdit()
        self.output_edit.setReadOnly(True)
        self.output_edit.setPlaceholderText(
            "Workflow logs and progress messages will appear here."
        )
        self.output_edit.document().setMaximumBlockCount(5_000)
        output_layout.addWidget(self.output_edit)

        input_group = QGroupBox("User input")
        input_layout = QVBoxLayout(input_group)
        self.prompt_label = QLabel(
            "No action is required. Login codes and questions will appear here."
        )
        self.prompt_label.setWordWrap(True)

        prompt_row = QHBoxLayout()
        self.prompt_edit = QLineEdit()
        self.prompt_edit.setPlaceholderText("Enter the requested value")
        self.prompt_edit.returnPressed.connect(self._submit_prompt)
        self.submit_prompt_button = QPushButton("Submit")
        self.submit_prompt_button.clicked.connect(self._submit_prompt)
        prompt_row.addWidget(self.prompt_edit, 1)
        prompt_row.addWidget(self.submit_prompt_button)

        input_layout.addWidget(self.prompt_label)
        input_layout.addLayout(prompt_row)

        splitter.addWidget(output_group)
        splitter.addWidget(input_group)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([440, 130])
        root.addWidget(splitter, 1)

        self._apply_styles()

    def _create_provider_combo(self) -> QComboBox:
        combo = QComboBox()
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
        self.setStyleSheet(
            """
            QLabel#titleLabel {
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#subtitleLabel {
                color: palette(mid);
                margin-bottom: 4px;
            }
            QGroupBox {
                font-weight: 600;
                border: 1px solid palette(midlight);
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 12px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QLineEdit, QComboBox, QPlainTextEdit {
                border: 1px solid palette(midlight);
                border-radius: 6px;
                padding: 7px;
            }
            QPushButton {
                border: 1px solid palette(midlight);
                border-radius: 6px;
                padding: 7px 14px;
            }
            QPushButton#primaryButton {
                font-weight: 700;
                padding-left: 20px;
                padding-right: 20px;
            }
            """
        )

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
        self.images_edit.setText(str(self._settings.value("images_directory", "")))
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
        self._settings.setValue("images_directory", self.images_edit.text().strip())
        self._settings.setValue("headless", self.headless_checkbox.isChecked())
        self._settings.setValue("verbose", self.verbose_checkbox.isChecked())

    def _browse_images_directory(self) -> None:
        initial = self.images_edit.text().strip() or str(Path.home())
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select listing images directory",
            initial,
        )
        if selected:
            self.images_edit.setText(selected)

    def _build_request(self) -> RelistRequest | None:
        listing_url = self.url_edit.text().strip()
        if not listing_url:
            self._validation_error("Enter the original listing URL.")
            return None

        images_text = self.images_edit.text().strip()
        images_path = Path(images_text) if images_text else None
        if images_path is not None:
            if not images_path.is_dir():
                self._validation_error(
                    f"The images path is not a directory:\n{images_path}"
                )
                return None
            if not (images_path / "instructions.txt").is_file():
                self._validation_error(
                    "instructions.txt was not found in the selected images "
                    f"directory:\n{images_path}"
                )
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
        self.status_label.setText("Cancelling...")
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
        else:
            logger.info("Dry run completed. No listing was published.")
            self.status_label.setText("Dry run completed")

    def _on_failure(self, error_message: str) -> None:
        self.status_label.setText("Relist failed")
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
        self.start_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.progress_bar.setVisible(running)

        for widget in (
            self.source_combo,
            self.destination_combo,
            self.url_edit,
            self.images_edit,
            self.browse_button,
            self.publish_checkbox,
            self.headless_checkbox,
            self.verbose_checkbox,
        ):
            widget.setEnabled(not running)

        if not running and not self._prompt_bridge.is_waiting:
            self.prompt_edit.setEnabled(False)
            self.submit_prompt_button.setEnabled(False)

    def _show_prompt(self, prompt: str, sensitive: bool) -> None:
        self.prompt_label.setText(prompt)
        self.prompt_edit.clear()
        self.prompt_edit.setEchoMode(
            QLineEdit.EchoMode.Password if sensitive else QLineEdit.EchoMode.Normal
        )
        self.prompt_edit.setEnabled(True)
        self.submit_prompt_button.setEnabled(True)
        self.prompt_edit.setFocus(Qt.FocusReason.OtherFocusReason)
        self.status_label.setText("Waiting for user input")

    def _submit_prompt(self) -> None:
        if not self._prompt_bridge.is_waiting:
            return
        response = self.prompt_edit.text()
        self.prompt_edit.setEnabled(False)
        self.submit_prompt_button.setEnabled(False)
        self._prompt_bridge.submit_response(response)
        self.status_label.setText("Continuing...")

    def _clear_prompt(self) -> None:
        self.prompt_label.setText(
            "No action is required. Login codes and questions will appear here."
        )
        self.prompt_edit.clear()
        self.prompt_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.prompt_edit.setEnabled(False)
        self.submit_prompt_button.setEnabled(False)

    def _append_log(self, message: str) -> None:
        self.output_edit.appendPlainText(message)
        scrollbar = self.output_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def output_clear(self) -> None:
        self.output_edit.clear()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_settings()

        if self._worker is None:
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
