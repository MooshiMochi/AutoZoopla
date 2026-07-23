from __future__ import annotations

from PySide6.QtWidgets import QWidget


class BasePage(QWidget):
    """Base class for a workspace page shown in the main window's stack.

    A page declares its sidebar label via :attr:`nav_label` and may react to
    becoming visible by overriding :meth:`on_activated`.
    """

    nav_label: str = ""

    def on_activated(self) -> None:
        """Called by the shell each time this page becomes the visible page."""

        return None
