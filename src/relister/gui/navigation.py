from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class NavItem:
    """A registered workspace page: sidebar key/label + a factory for its widget."""

    key: str
    label: str
    factory: Callable[[], QWidget]
