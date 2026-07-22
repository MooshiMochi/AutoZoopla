"""Shared visual system for the AutoZoopla desktop app.

Single source of truth for the palette, type scale and component styling used by
both the relist window and the image organiser (embedded and standalone). Also
hosts the custom-painted widgets that keep inputs consistent across platforms.

The design-token constants below MUST stay in sync with the hex values used in
``_STYLESHEET`` (kept literal there to avoid brace-escaping in the QSS).
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QCheckBox, QComboBox, QStyleOptionButton

# --------------------------------------------------------------------- tokens
BACKGROUND = "#f5f7fc"
SIDEBAR = "#0f172a"
CARD = "#ffffff"
BORDER = "#e6eaf2"

TEXT = "#0f172a"
TEXT_SECONDARY = "#475569"
TEXT_MUTED = "#94a3b8"

ACCENT = "#4f46e5"
ACCENT_HOVER = "#4338ca"
ACCENT_SOFT = "#eef2ff"

CHECK_BORDER = "#9aa6ba"
CHEVRON = "#64748b"


class ChevronCombo(QComboBox):
    """Combo box that paints its own chevron.

    The native drop-down indicator is hidden via QSS; painting the arrow here
    means it can never clip the rounded border the way the platform indicator
    does.
    """

    def paintEvent(self, event: object) -> None:  # noqa: D401 - Qt override
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center_x = self.width() - 20
        center_y = self.height() / 2
        pen = QPen(QColor(CHEVRON if self.isEnabled() else TEXT_MUTED), 1.8)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolyline(
            QPolygonF(
                [
                    QPointF(center_x - 5, center_y - 3),
                    QPointF(center_x, center_y + 3),
                    QPointF(center_x + 5, center_y - 3),
                ]
            )
        )


class ModernCheckBox(QCheckBox):
    """A consistently rendered checkbox that remains visible on hover.

    Painted by hand so the indicator looks the same across platforms and styling
    stays tied to the accent token.
    """

    _INDICATOR_SIZE = 19
    _INDICATOR_SPACING = 9

    def sizeHint(self) -> QSize:
        metrics = self.fontMetrics()
        width = (
            self._INDICATOR_SIZE
            + self._INDICATOR_SPACING
            + metrics.horizontalAdvance(self.text())
            + 4
        )
        return QSize(width, max(30, metrics.height() + 8))

    def paintEvent(self, event: object) -> None:  # noqa: D401 - Qt override
        option = QStyleOptionButton()
        self.initStyleOption(option)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        enabled = self.isEnabled()
        hovered = self.underMouse()
        checked = self.checkState() == Qt.CheckState.Checked
        partial = self.checkState() == Qt.CheckState.PartiallyChecked

        indicator_y = (self.height() - self._INDICATOR_SIZE) / 2
        indicator = QRectF(
            0.75,
            indicator_y + 0.75,
            self._INDICATOR_SIZE - 1.5,
            self._INDICATOR_SIZE - 1.5,
        )

        if not enabled:
            fill = QColor("#f1f5f9")
            border = QColor("#cbd5e1")
        elif checked or partial:
            fill = QColor(ACCENT_HOVER if hovered else ACCENT)
            border = fill
        elif hovered:
            fill = QColor(ACCENT_SOFT)
            border = QColor(ACCENT)
        else:
            fill = QColor("#ffffff")
            border = QColor(CHECK_BORDER)

        painter.setPen(QPen(border, 1.4))
        painter.setBrush(fill)
        painter.drawRoundedRect(indicator, 5.0, 5.0)

        if checked:
            check_pen = QPen(QColor("#ffffff"), 2.1)
            check_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            check_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(check_pen)
            x = indicator.left()
            y = indicator.top()
            painter.drawLine(QPointF(x + 4.4, y + 9.6), QPointF(x + 7.8, y + 12.9))
            painter.drawLine(QPointF(x + 7.8, y + 12.9), QPointF(x + 14.4, y + 5.9))
        elif partial:
            partial_pen = QPen(QColor("#ffffff"), 2.2)
            partial_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(partial_pen)
            painter.drawLine(
                QPointF(indicator.left() + 4.4, indicator.center().y()),
                QPointF(indicator.right() - 4.4, indicator.center().y()),
            )

        text_rect = QRectF(
            self._INDICATOR_SIZE + self._INDICATOR_SPACING,
            0,
            max(0, self.width() - self._INDICATOR_SIZE - self._INDICATOR_SPACING),
            self.height(),
        )
        painter.setPen(QColor(TEXT_SECONDARY if enabled else TEXT_MUTED))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.text(),
        )

        if self.hasFocus():
            focus_pen = QPen(QColor("#c7d2fe"), 1.0, Qt.PenStyle.DotLine)
            painter.setPen(focus_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 5, 5)


_STYLESHEET = """
* {
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: #0f172a;
}
QMainWindow, QFrame#appRoot, QStackedWidget#pageStack, QWidget#relistPage,
QWidget#imageOrderPage, QWidget#windowRoot, QWidget#relistBody,
QWidget#promptContainer {
    background: #f5f7fc;
}
QScrollArea, QScrollArea > QWidget > QWidget#relistBody {
    background: #f5f7fc;
    border: none;
}
QToolTip {
    color: #0f172a;
    background: #ffffff;
    border: 1px solid #e6eaf2;
    padding: 6px 8px;
    border-radius: 6px;
}

/* Dialogs & menus: force a light surface so text stays readable even when the
   OS is in dark mode (the global colour above is dark and would otherwise be
   dark-on-dark on an unstyled message box or menu). */
QDialog, QMessageBox, QInputDialog { background: #ffffff; }
QMessageBox QLabel, QInputDialog QLabel, QDialog QLabel { color: #0f172a; background: transparent; }
QMenu { background: #ffffff; border: 1px solid #e6eaf2; border-radius: 8px; padding: 4px; }
QMenu::item { padding: 6px 24px 6px 12px; border-radius: 6px; color: #0f172a; }
QMenu::item:selected { background: #eef2ff; color: #0f172a; }
QMenu::separator { height: 1px; background: #eef1f7; margin: 4px 6px; }

/* Sidebar ------------------------------------------------------------------ */
QFrame#sidebar { background: #0f172a; border: none; }
QLabel#brandMark {
    background: #4f46e5; color: #ffffff; border-radius: 12px;
    font-size: 15px; font-weight: 800;
}
QLabel#brandTitle { color: #f8fafc; font-size: 15px; font-weight: 700; }
QLabel#brandSubtitle { color: #7c8aa5; font-size: 11.5px; }
QLabel#sidebarSection {
    color: #64748b; font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
    padding: 2px 10px;
}
QPushButton#navButton {
    min-height: 38px; padding: 0 14px; text-align: left; color: #cbd5e1;
    background: transparent; border: none; border-radius: 10px; font-weight: 600;
}
QPushButton#navButton:hover { background: #1e293b; color: #ffffff; }
QPushButton#navButton:checked { background: #4f46e5; color: #ffffff; }
QLabel#sidebarHint {
    color: #94a3b8; background: #131e33; border: 1px solid #24324b;
    border-radius: 12px; padding: 13px; line-height: 1.5;
}

/* Headings & badges -------------------------------------------------------- */
QLabel#pageTitle, QLabel#titleLabel { color: #0f172a; font-size: 21px; font-weight: 700; }
QLabel#pageSubtitle, QLabel#subtitleLabel { color: #5b6576; font-size: 13px; }
QLabel#runBadge {
    min-width: 70px; padding: 5px 11px; border-radius: 8px; font-size: 10.5px;
    font-weight: 800; letter-spacing: 0.6px;
}
QLabel#runBadge[state="ready"] { color: #15803d; background: #dcfce7; border: 1px solid #bbf7d0; }
QLabel#runBadge[state="running"] { color: #4338ca; background: #eef2ff; border: 1px solid #c7d2fe; }
QLabel#runBadge[state="attention"] { color: #c2410c; background: #ffedd5; border: 1px solid #fed7aa; }

/* Cards -------------------------------------------------------------------- */
QFrame#card, QFrame#toolbarCard, QFrame#statusCard, QFrame#actionBar {
    background: #ffffff; border: 1px solid #e6eaf2; border-radius: 14px;
}
QLabel#cardTitle { color: #0f172a; font-size: 14px; font-weight: 700; }
QLabel#cardSubtitle, QLabel#previewLabel { color: #94a3b8; font-size: 12px; }
QLabel#groupLabel { color: #94a3b8; font-size: 11px; font-weight: 700; letter-spacing: 1px; }
QLabel#fieldLabel { color: #475569; font-size: 12.5px; font-weight: 600; }
QFrame#divider { background: #eef1f7; max-height: 1px; min-height: 1px; border: none; }

/* Inputs ------------------------------------------------------------------- */
QLineEdit, QComboBox, QPlainTextEdit {
    background: #ffffff; border: 1px solid #d3dae7; border-radius: 10px;
    padding: 0 12px; selection-background-color: #4f46e5; selection-color: #ffffff;
}
QLineEdit, QComboBox { min-height: 34px; }
QLineEdit:hover, QComboBox:hover { border-color: #aab6c9; }
QLineEdit:focus, QComboBox:focus { border: 2px solid #4f46e5; padding: 0 11px; }
QLineEdit:disabled, QComboBox:disabled {
    color: #94a3b8; background: #f1f5f9; border-color: #e2e8f0;
}
QComboBox::drop-down { border: none; width: 30px; }
QComboBox::down-arrow { image: none; width: 0; height: 0; }
QComboBox QAbstractItemView {
    color: #0f172a; background: #ffffff; border: 1px solid #d9e0eb;
    border-radius: 8px; padding: 4px; selection-background-color: #eef2ff;
    selection-color: #0f172a; outline: none;
}

/* Buttons ------------------------------------------------------------------ */
QPushButton {
    min-height: 34px; padding: 0 14px; border: 1px solid #d3dae7;
    border-radius: 9px; background: #ffffff; color: #334155; font-weight: 650;
}
QPushButton:hover { background: #f7f9fc; border-color: #aab6c9; }
QPushButton:pressed { background: #eef2f8; }
QPushButton:disabled { color: #a3adbd; background: #f1f4f9; border-color: #e6eaf2; }
QPushButton#primaryButton, QPushButton#attentionButton {
    color: #ffffff; background: #4f46e5; border-color: #4f46e5; font-weight: 750;
}
QPushButton#primaryButton:hover, QPushButton#attentionButton:hover {
    background: #4338ca; border-color: #4338ca;
}
QPushButton#primaryButton:disabled, QPushButton#attentionButton:disabled {
    color: #ffffff; background: #b7b4ee; border-color: #b7b4ee;
}
QPushButton#secondaryAccentButton {
    color: #4338ca; background: #eef2ff; border-color: #c7d2fe;
}
QPushButton#secondaryAccentButton:hover { background: #e2e8ff; border-color: #a5b4fc; }
QPushButton#dangerButton:enabled { color: #b91c1c; background: #fef2f2; border-color: #fecaca; }
QPushButton#dangerButton:enabled:hover { background: #fee2e2; border-color: #fca5a5; }
QPushButton#inlineActionButton {
    min-height: 30px; color: #c2410c; background: transparent; border: 1px solid #fdba74;
}
QPushButton#inlineActionButton:hover { background: #fff7ed; }

/* Top banner (overlays the top of the relist page) -------------------------- */
QFrame#topBanner { background: #fff7ed; border: none; border-bottom: 1px solid #fed7aa; }
QFrame#topBanner[state="success"] { background: #f0fdf4; border-bottom: 1px solid #bbf7d0; }
QFrame#topBanner[state="error"] { background: #fef2f2; border-bottom: 1px solid #fecaca; }
QLabel#topBannerIcon {
    color: #c2410c; background: #ffedd5; border-radius: 12px; font-weight: 800;
}
QFrame#topBanner[state="success"] QLabel#topBannerIcon { color: #15803d; background: #dcfce7; }
QFrame#topBanner[state="error"] QLabel#topBannerIcon { color: #b91c1c; background: #fee2e2; }
QLabel#topBannerText { color: #9a3412; font-size: 12.5px; font-weight: 600; }
QFrame#topBanner[state="success"] QLabel#topBannerText { color: #15803d; }
QFrame#topBanner[state="error"] QLabel#topBannerText { color: #b91c1c; }
QPushButton#topBannerClose {
    min-height: 30px; padding: 0; border: none; border-radius: 15px;
    background: transparent; color: #64748b; font-size: 21px; font-weight: 500;
}
QPushButton#topBannerClose:hover { background: #ffffffaa; color: #334155; }
QPushButton#topBannerClose:pressed { background: #ffffffdd; }

QLabel#imageStatusLabel {
    font-size: 11.5px; font-weight: 650;
}
QLabel#imageStatusLabel[state="success"] { color: #15803d; }
QLabel#imageStatusLabel[state="error"] { color: #b91c1c; }
QLabel#imageStatusLabel[state="warning"] { color: #c2410c; }

/* Console & workflow status ------------------------------------------------ */
QPlainTextEdit#logOutput {
    color: #cbd5e1; background: #0b1220; border: 1px solid #1e293b;
    border-radius: 12px; font-family: "Cascadia Mono", "Consolas", monospace;
    font-size: 12.5px; padding: 12px;
}
QProgressBar {
    min-height: 8px; max-height: 8px; border: none; border-radius: 4px; background: #dbe3ef;
}
QProgressBar::chunk { border-radius: 4px; background: #4f46e5; }
QLabel#workflowStatus { color: #5b6576; font-weight: 600; }

/* User input section ------------------------------------------------------- */
QFrame#promptCard { background: #ffffff; border: 1px solid #e6eaf2; border-radius: 12px; }
QFrame#promptCard[active="true"] { border: 1px solid #c7d2fe; background: #fcfcff; }
QLabel#promptTitle { color: #0f172a; font-size: 14px; font-weight: 750; }
QLabel#promptBadge {
    color: #64748b; background: #f1f5f9; border-radius: 8px; padding: 4px 10px;
    font-size: 10px; font-weight: 800;
}
QFrame#promptCard[active="true"] QLabel#promptBadge { color: #4338ca; background: #eef2ff; }
QLabel#promptMessage { color: #475569; font-weight: 600; }
/* The input box glows with the accent border while input is requested. */
QLineEdit#promptInput[active="true"] { border: 2px solid #4f46e5; }

/* Organiser ---------------------------------------------------------------- */
QLabel#pathLabel, QLabel#pathChip {
    color: #475569; background: #f7f9fc; border: 1px solid #e6eaf2;
    border-radius: 10px; padding: 9px 12px;
}
QLabel#statusLabel { color: #5b6576; }
QFrame#emptyState { background: #ffffff; border: 1.5px dashed #cbd5e1; border-radius: 16px; }
QLabel#emptyGlyph {
    background: #eef2ff; color: #4f46e5; border-radius: 20px; font-size: 26px; font-weight: 800;
}
QLabel#emptyTitle { color: #0f172a; font-size: 16px; font-weight: 700; }
QLabel#emptyBody { color: #64748b; font-size: 13px; }

QListWidget#imageGrid { background: transparent; border: none; outline: none; }
QListWidget#imageGrid::item { background: transparent; border: none; }
QFrame#imageCard { background: #ffffff; border: 1px solid #e6eaf2; border-radius: 14px; }
QFrame#imageCard:hover { border-color: #a5b4fc; }
QLabel#thumbnailLabel {
    background: #eef2f8; border: 1px solid #e2e8f0; border-radius: 10px; color: #94a3b8;
}
QLabel#filenameLabel { color: #253047; font-weight: 600; font-size: 12px; }
QComboBox[visibilityState="visible"] { color: #147447; background: #eaf8f0; border: 1px solid #bee7cf; }
QComboBox[visibilityState="hidden"] { color: #697386; background: #f0f2f5; border: 1px solid #d9dee7; }

/* Organiser drag skeleton -------------------------------------------------- */
QFrame#skeletonCard { background: #eef2ff; border: 2px dashed #a5b4fc; border-radius: 14px; }
QFrame#skeletonImage, QFrame#skeletonLine { background: #dbe3f6; border: none; border-radius: 8px; }
QLabel#skeletonText { color: #6d7fb0; font-weight: 700; }

/* Sliders ------------------------------------------------------------------ */
QSlider::groove:horizontal { height: 5px; border-radius: 2px; background: #dce3ee; }
QSlider::sub-page:horizontal { border-radius: 2px; background: #6366f1; }
QSlider::handle:horizontal { width: 16px; margin: -6px 0; border-radius: 8px; background: #4f46e5; }

/* Scrollbars --------------------------------------------------------------- */
QScrollBar:vertical { width: 11px; background: transparent; margin: 2px; }
QScrollBar::handle:vertical { min-height: 30px; background: #cbd5e1; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #b3bdcc; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 11px; background: transparent; margin: 2px; }
QScrollBar::handle:horizontal { min-width: 30px; background: #cbd5e1; border-radius: 5px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
"""


def build_stylesheet() -> str:
    """Return the application-wide Qt stylesheet."""

    return _STYLESHEET
