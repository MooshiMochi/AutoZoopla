from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ...providers.zoopla import selectors
from ...storage.app_settings import AppSettings
from ...storage.credentials import CredentialStore
from ..theme import ModernCheckBox
from ..widgets.form_helpers import field_label, section_row
from ..widgets.top_banner import TopBanner
from .base_page import BasePage


class SettingsPage(BasePage):
    """Central place to edit provider credentials and provider settings.

    Replaces the per-dropdown gear dialogs: credentials are saved (encrypted)
    to the :class:`CredentialStore`, and non-secret settings such as the Zoopla
    Branch ID to :class:`AppSettings`.
    """

    nav_label = "Settings"

    def __init__(
        self,
        credentials: CredentialStore,
        app_settings: AppSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._credentials = credentials
        self._app_settings = app_settings
        self._build_ui()
        self.on_activated()

    # ------------------------------------------------------------------ build

    def _build_ui(self) -> None:
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        page_layout.addWidget(scroll, 1)

        self.top_banner = TopBanner(self)

        body = QWidget()
        body.setObjectName("settingsBody")
        root = QVBoxLayout(body)
        root.setContentsMargins(20, 14, 20, 14)
        root.setSpacing(9)
        scroll.setWidget(body)

        subtitle = QLabel(
            "Enter provider sign-in details and settings. Credentials are stored "
            "encrypted on this machine and never leave it."
        )
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        root.addWidget(self._build_credentials_card())
        root.addWidget(self._build_zoopla_card())

        # Action bar --------------------------------------------------------
        action_bar = QFrame()
        action_bar.setObjectName("actionBar")
        action_bar.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
        )
        actions = QHBoxLayout(action_bar)
        actions.setContentsMargins(14, 8, 14, 8)
        actions.setSpacing(10)

        self.save_button = QPushButton("Save settings")
        self.save_button.setObjectName("primaryButton")
        self.save_button.clicked.connect(self._save)

        self.show_passwords = ModernCheckBox("Show passwords")
        self.show_passwords.toggled.connect(self._toggle_password_visibility)

        self.status_label = QLabel("")
        self.status_label.setObjectName("workflowStatus")
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        actions.addWidget(self.save_button)
        actions.addWidget(self.show_passwords)
        actions.addWidget(self.status_label, 1)
        root.addWidget(action_bar)
        root.addStretch(1)

    def _build_credentials_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        title = QLabel("Zoopla credentials")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        self._password_edits: list[QLineEdit] = []
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(4)
        grid.addWidget(field_label("Source username / email"), 0, 0)
        grid.addWidget(field_label("Source password"), 0, 1)
        self.source_username = QLineEdit()
        self.source_password = self._password_field()
        grid.addWidget(self.source_username, 1, 0)
        grid.addWidget(self.source_password, 1, 1)
        grid.addWidget(field_label("Destination username / email"), 2, 0)
        grid.addWidget(field_label("Destination password"), 2, 1)
        self.destination_username = QLineEdit()
        self.destination_password = self._password_field()
        grid.addWidget(self.destination_username, 3, 0)
        grid.addWidget(self.destination_password, 3, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(section_row("ZOOPLA", grid))
        return card

    def _build_zoopla_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        title = QLabel("Zoopla settings")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        content = QVBoxLayout()
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(4)
        content.addWidget(field_label("Branch ID"))
        self.branch_id_edit = QLineEdit()
        self.branch_id_edit.setPlaceholderText(selectors.BRANCH_ID)
        content.addWidget(self.branch_id_edit)
        layout.addLayout(section_row("BRANCH", content))
        return card

    def _password_field(self) -> QLineEdit:
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edits.append(edit)
        return edit

    # ---------------------------------------------------------------- persist

    def on_activated(self) -> None:
        source = self._credentials.get("zoopla", "source")
        if source:
            self.source_username.setText(source[0])
            self.source_password.setText(source[1])
        destination = self._credentials.get("zoopla", "destination")
        if destination:
            self.destination_username.setText(destination[0])
            self.destination_password.setText(destination[1])
        self.branch_id_edit.setText(
            self._app_settings.get("zoopla_branch_id") or ""
        )

    def _toggle_password_visibility(self, visible: bool) -> None:
        mode = (
            QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
        )
        for edit in self._password_edits:
            edit.setEchoMode(mode)

    def resizeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().resizeEvent(event)
        self.top_banner.reposition()

    def _save(self) -> None:
        try:
            self._credentials.set(
                "zoopla",
                "source",
                self.source_username.text().strip(),
                self.source_password.text(),
            )
            self._credentials.set(
                "zoopla",
                "destination",
                self.destination_username.text().strip(),
                self.destination_password.text(),
            )
            branch_id = self.branch_id_edit.text().strip()
            if branch_id:
                self._app_settings.set("zoopla_branch_id", branch_id)
        except Exception as exc:
            self.status_label.setText("Could not save settings.")
            self.top_banner.show_banner("error", f"Could not save settings: {exc}")
            return
        self.status_label.setText("Settings saved.")
        self.top_banner.show_banner("success", "Credentials and settings saved.")
