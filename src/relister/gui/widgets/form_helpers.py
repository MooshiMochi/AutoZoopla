from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel


def section_row(tag_text: str, content_layout) -> QHBoxLayout:
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


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    return label
