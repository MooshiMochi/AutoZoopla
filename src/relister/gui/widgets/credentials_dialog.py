from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ...storage.credentials import CredentialStore


class CredentialsDialog(QDialog):
    """Edit and save a provider account's username/password (encrypted)."""

    def __init__(
        self,
        provider_key: str,
        role: str,
        store: CredentialStore,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._provider_key = provider_key
        self._role = role
        self._store = store

        self.setWindowTitle(f"{provider_key.title()} {role} credentials")
        self.setModal(True)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setContentsMargins(4, 4, 4, 4)
        form.setSpacing(10)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Username or email")

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Password")

        self.reveal_button = QToolButton()
        self.reveal_button.setText("Show")
        self.reveal_button.setCheckable(True)
        self.reveal_button.toggled.connect(self._toggle_reveal)

        form.addRow("Username / email", self.username_edit)
        form.addRow("Password", self.password_edit)
        form.addRow("", self.reveal_button)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._prefill()

    def _prefill(self) -> None:
        existing = self._store.get(self._provider_key, self._role)
        if existing:
            self.username_edit.setText(existing[0])
            self.password_edit.setText(existing[1])

    def _toggle_reveal(self, revealed: bool) -> None:
        self.password_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if revealed else QLineEdit.EchoMode.Password
        )
        self.reveal_button.setText("Hide" if revealed else "Show")

    def _on_save(self) -> None:
        self._store.set(
            self._provider_key,
            self._role,
            self.username_edit.text().strip(),
            self.password_edit.text(),
        )
        self.accept()
