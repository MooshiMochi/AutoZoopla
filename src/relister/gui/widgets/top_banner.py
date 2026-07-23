from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QRect, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget


class TopBanner(QFrame):
    """A full-width status banner that slides down over the top of its parent page.

    The parent page is responsible for calling :meth:`reposition` from its
    ``resizeEvent`` so the banner tracks the page width.
    """

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("topBanner")
        self.setProperty("state", "success")
        self.setGeometry(0, 0, parent.width(), 0)
        self.setVisible(False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 9, 18, 9)
        layout.setSpacing(10)

        self.icon = QLabel("!")
        self.icon.setObjectName("topBannerIcon")
        self.icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon.setFixedSize(24, 24)

        self.label = QLabel("")
        self.label.setObjectName("topBannerText")
        self.label.setWordWrap(True)

        self.close_button = QPushButton("×")
        self.close_button.setObjectName("topBannerClose")
        self.close_button.setAccessibleName("Close status banner")
        self.close_button.setToolTip("Close status banner")
        self.close_button.setFixedSize(30, 30)
        self.close_button.clicked.connect(self.hide_banner)

        layout.addWidget(self.icon)
        layout.addWidget(self.label, 1)
        layout.addWidget(self.close_button)

        self._anim = QPropertyAnimation(self, b"geometry", self)
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.finished.connect(self._finish_animation)
        self._hiding = False

    def _set_dynamic_property(self, name: str, value: Any) -> None:
        self.setProperty(name, value)
        style = self.style()
        style.unpolish(self)
        style.polish(self)
        self.update()

    def reposition(self) -> None:
        self.setGeometry(0, 0, self.parentWidget().width(), self.height())
        self.raise_()

    def show_banner(self, state: str, message: str) -> None:
        self.label.setText(message)
        self.icon.setText("✓" if state == "success" else "!")
        self._set_dynamic_property("state", state)

        width = self.parentWidget().width()
        target_height = self.sizeHint().height()
        start_height = self.height() if self.isVisible() else 0
        start = QRect(0, 0, width, start_height)
        end = QRect(0, 0, width, target_height)
        self._anim.stop()
        self._hiding = False
        self.setGeometry(start)
        self.setVisible(True)
        self.raise_()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

    def hide_banner(self) -> None:
        if self.isHidden() and self.height() == 0:
            return
        width = self.parentWidget().width()
        start = self.geometry()
        end = QRect(0, 0, width, 0)
        self._anim.stop()
        self._hiding = True
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

    def _finish_animation(self) -> None:
        if self._hiding:
            self.setGeometry(0, 0, self.parentWidget().width(), 0)
            self.setVisible(False)
            self._hiding = False
        else:
            self.setVisible(True)
            self.reposition()
