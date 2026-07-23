from __future__ import annotations

from typing import Any

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)
from PySide6.QtCore import Signal

_IDLE_MESSAGE = (
    "This box stays disabled until the workflow needs a login code or an "
    "answer to continue."
)


class PromptPanel(QFrame):
    """The always-present user-input section beneath the console.

    Disabled by default; :meth:`show_prompt` lights it up (with an accent glow)
    when the workflow needs input. Emits :attr:`submitted` with the entered text.
    Window-level attention (raise/focus/beep) and the prompt-bridge wiring stay
    with the owning page.
    """

    submitted = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("promptCard")
        self.setProperty("active", False)
        from PySide6.QtWidgets import QSizePolicy

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self.title = QLabel("User input")
        self.title.setObjectName("promptTitle")
        self.badge = QLabel("NO INPUT NEEDED")
        self.badge.setObjectName("promptBadge")
        header.addWidget(self.title)
        header.addStretch(1)
        header.addWidget(self.badge)
        layout.addLayout(header)

        self.message = QLabel(_IDLE_MESSAGE)
        self.message.setObjectName("promptMessage")
        self.message.setWordWrap(True)
        layout.addWidget(self.message)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.edit = QLineEdit()
        self.edit.setObjectName("promptInput")
        self.edit.setProperty("active", False)
        self.edit.setPlaceholderText("Enter the requested value")
        self.edit.setEnabled(False)
        self.edit.returnPressed.connect(self._emit_submitted)
        self.submit_button = QPushButton("Submit response")
        self.submit_button.setObjectName("attentionButton")
        self.submit_button.setEnabled(False)
        self.submit_button.clicked.connect(self._emit_submitted)
        row.addWidget(self.edit, 1)
        row.addWidget(self.submit_button)
        layout.addLayout(row)

        self._glow = QGraphicsDropShadowEffect(self.edit)
        self._glow.setBlurRadius(16)
        self._glow.setOffset(0, 0)
        self._glow.setColor(QColor(79, 70, 229, 190))
        self._glow.setEnabled(False)
        self.edit.setGraphicsEffect(self._glow)

    def _set_dynamic_property(self, widget, name: str, value: Any) -> None:
        widget.setProperty(name, value)
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def set_active(self, active: bool) -> None:
        """Toggle the accent glow + border while input is requested."""

        self._glow.setEnabled(active)
        self._set_dynamic_property(self.edit, "active", active)
        self._set_dynamic_property(self, "active", active)

    def _emit_submitted(self) -> None:
        self.submitted.emit(self.edit.text())

    def show_prompt(self, prompt: str, sensitive: bool) -> None:
        self.title.setText("Action required")
        self.badge.setText("INPUT REQUIRED")
        self.message.setText(prompt)
        self.edit.clear()
        self.edit.setEchoMode(
            QLineEdit.EchoMode.Password if sensitive else QLineEdit.EchoMode.Normal
        )
        self.edit.setEnabled(True)
        self.submit_button.setEnabled(True)
        self.set_active(True)

    def focus_input(self) -> None:
        from PySide6.QtCore import Qt

        self.edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def mark_submitted(self) -> None:
        self.edit.setEnabled(False)
        self.submit_button.setEnabled(False)
        self.set_active(False)
        self.badge.setText("SUBMITTED")
        self.message.setText("Response submitted. The workflow is continuing…")

    def clear(self) -> None:
        self.set_active(False)
        self.title.setText("User input")
        self.badge.setText("NO INPUT NEEDED")
        self.message.setText(_IDLE_MESSAGE)
        self.edit.clear()
        self.edit.setEchoMode(QLineEdit.EchoMode.Normal)
        self.edit.setEnabled(False)
        self.submit_button.setEnabled(False)
