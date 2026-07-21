from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from PySide6.QtCore import (
    QDir,
    QObject,
    QPoint,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    QTimer,
    Signal,
    Slot,
)
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QFocusEvent,
    QImage,
    QImageReader,
    QKeyEvent,
    QMouseEvent,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

SUPPORTED_EXTENSIONS = {
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}

INSTRUCTIONS_FILENAME = "instructions.txt"
DEFAULT_THUMBNAIL_SIZE = 104
MIN_THUMBNAIL_SIZE = 56
MAX_THUMBNAIL_SIZE = 180


APP_STYLE = """
QMainWindow, QWidget#windowRoot {
    background: #f5f7fb;
    color: #172033;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 10pt;
}

QFrame#toolbarCard, QFrame#statusCard {
    background: #ffffff;
    border: 1px solid #dfe5ee;
    border-radius: 14px;
}

QLabel#titleLabel {
    color: #111827;
    font-size: 18pt;
    font-weight: 700;
}

QLabel#subtitleLabel, QLabel#pathLabel, QLabel#statusLabel,
QLabel#previewLabel {
    color: #657087;
}

QLabel#pathLabel {
    background: #f7f9fc;
    border: 1px solid #e1e7f0;
    border-radius: 8px;
    padding: 7px 10px;
}

QPushButton {
    min-height: 34px;
    padding: 0 16px;
    border-radius: 8px;
    border: 1px solid #cfd7e4;
    background: #ffffff;
    color: #273449;
    font-weight: 600;
}

QPushButton:hover {
    background: #f3f6fa;
    border-color: #aeb9c9;
}

QPushButton:pressed {
    background: #e9eef5;
}

QPushButton#primaryButton {
    background: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
}

QPushButton#primaryButton:hover {
    background: #1d4ed8;
    border-color: #1d4ed8;
}

QPushButton:disabled {
    background: #edf1f6;
    border-color: #e1e6ee;
    color: #9aa5b4;
}

QSlider::groove:horizontal {
    height: 5px;
    border-radius: 2px;
    background: #dce3ee;
}

QSlider::sub-page:horizontal {
    border-radius: 2px;
    background: #5b84ee;
}

QSlider::handle:horizontal {
    width: 16px;
    margin: -6px 0;
    border-radius: 8px;
    background: #2563eb;
}

QListWidget#imageGrid {
    background: transparent;
    border: none;
    outline: none;
}

QListWidget#imageGrid::item {
    background: transparent;
    border: none;
}

QFrame#imageCard {
    background: #ffffff;
    border: 1px solid #dfe5ee;
    border-radius: 13px;
}

QFrame#imageCard:hover {
    border-color: #9db5f5;
}

QLabel#thumbnailLabel {
    background: #eef2f7;
    border: 1px solid #e0e6ef;
    border-radius: 10px;
    color: #7a8699;
}

QLabel#filenameLabel {
    color: #253047;
    font-weight: 600;
}

QComboBox {
    min-height: 29px;
    padding: 0 9px;
    border-radius: 7px;
    font-weight: 600;
}

QComboBox[visibilityState="visible"] {
    color: #147447;
    background: #eaf8f0;
    border: 1px solid #bee7cf;
}

QComboBox[visibilityState="hidden"] {
    color: #697386;
    background: #f0f2f5;
    border: 1px solid #d9dee7;
}

QComboBox::drop-down {
    width: 22px;
    border: none;
}

QComboBox QAbstractItemView {
    color: #172033;
    background: #ffffff;
    border: 1px solid #d9e0eb;
    selection-background-color: #e9efff;
    selection-color: #172033;
}

QFrame#skeletonCard {
    background: #f0f4fb;
    border: 2px dashed #8da8df;
    border-radius: 13px;
}

QFrame#skeletonImage, QFrame#skeletonLine {
    background: #dce5f4;
    border: none;
    border-radius: 8px;
}

QLabel#skeletonText {
    color: #6880ae;
    font-weight: 700;
}
"""


@dataclass(frozen=True)
class ImageEntry:
    path: Path
    filename: str
    visible: bool = True


@dataclass(frozen=True)
class ImageCardPayload:
    path: str
    filename: str
    visible: bool
    source_image: QImage | None
    thumbnail_state: str


class ThumbnailSignals(QObject):
    loaded = Signal(int, str, object)


class ThumbnailTask(QRunnable):
    def __init__(self, path: Path, generation: int) -> None:
        super().__init__()
        self.path = path
        self.generation = generation
        self.signals = ThumbnailSignals()

    @Slot()
    def run(self) -> None:
        reader = QImageReader(str(self.path))
        reader.setAutoTransform(True)
        image = reader.read()
        self.signals.loaded.emit(self.generation, self.path.name, image)


def is_supported_image(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS


def load_images(directory: Path) -> list[ImageEntry]:
    return [
        ImageEntry(path=item, filename=item.name)
        for item in sorted(
            directory.iterdir(),
            key=lambda file_path: file_path.name.casefold(),
        )
        if is_supported_image(item)
    ]


def parse_instruction_order(
    directory: Path,
    images: list[ImageEntry],
) -> list[ImageEntry]:
    """Apply order and visibility from `instructions.txt`.

    The file uses the raw image filenames, one per line.
    - Listed files are ordered first and marked visible.
    - Files not listed are kept, but shifted after the ordered ones and marked hidden.
    """
    instructions_path = directory / INSTRUCTIONS_FILENAME
    if not instructions_path.exists():
        return images

    try:
        requested_names = [
            line.strip()
            for line in instructions_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError:
        return images

    by_name = {entry.filename: entry for entry in images}
    ordered_entries: list[ImageEntry] = []
    seen: set[str] = set()

    for filename in requested_names:
        if filename in seen:
            continue
        entry = by_name.get(filename)
        if entry is None:
            continue
        ordered_entries.append(replace(entry, visible=True))
        seen.add(filename)

    ordered_entries.extend(
        replace(entry, visible=False) for entry in images if entry.filename not in seen
    )
    return ordered_entries


def item_card_size(thumbnail_size: int) -> QSize:
    width = max(172, thumbnail_size + 36)
    height = thumbnail_size + 112
    return QSize(width, height)


def item_grid_size(thumbnail_size: int) -> QSize:
    card_size = item_card_size(thumbnail_size)
    return QSize(card_size.width() + 16, card_size.height() + 16)


def write_text_atomic(path: Path, content: str) -> None:
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(content, encoding="utf-8")
    temporary_path.replace(path)


class SkeletonCard(QFrame):
    def __init__(self, thumbnail_size: int) -> None:
        super().__init__()
        self.setObjectName("skeletonCard")

        self.image_block = QFrame()
        self.image_block.setObjectName("skeletonImage")

        self.line_one = QFrame()
        self.line_one.setObjectName("skeletonLine")
        self.line_one.setFixedHeight(12)

        self.line_two = QFrame()
        self.line_two.setObjectName("skeletonLine")
        self.line_two.setFixedHeight(10)

        self.drop_label = QLabel("Drop here")
        self.drop_label.setObjectName("skeletonText")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self.image_block, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.line_one, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.line_two, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        layout.addWidget(self.drop_label)

        self.set_thumbnail_size(thumbnail_size)

    def set_thumbnail_size(self, thumbnail_size: int) -> None:
        self.image_block.setFixedSize(thumbnail_size, thumbnail_size)
        content_width = max(132, thumbnail_size)
        self.line_one.setFixedWidth(int(content_width * 0.78))
        self.line_two.setFixedWidth(int(content_width * 0.56))


class ImageItemWidget(QFrame):
    def __init__(self, filename: str, visible: bool, thumbnail_size: int) -> None:
        super().__init__()
        self.filename = filename
        self.source_image: QImage | None = None
        self.thumbnail_state = "loading"
        self.setObjectName("imageCard")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        self.thumbnail_label = QLabel("Loading…")
        self.thumbnail_label.setObjectName("thumbnailLabel")
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setScaledContents(False)
        self.thumbnail_label.setCursor(Qt.CursorShape.OpenHandCursor)

        self.name_label = QLabel(filename)
        self.name_label.setObjectName("filenameLabel")
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setWordWrap(True)
        self.name_label.setToolTip(filename)
        self.name_label.setCursor(Qt.CursorShape.OpenHandCursor)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["Visible", "Hidden"])
        self.status_combo.setCurrentText("Visible" if visible else "Hidden")
        self.status_combo.currentTextChanged.connect(self._refresh_visibility_style)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(8)
        content_layout.addWidget(
            self.thumbnail_label,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )
        content_layout.addWidget(self.name_label)
        content_layout.addStretch(1)
        content_layout.addWidget(self.status_combo)

        self.skeleton = SkeletonCard(thumbnail_size)

        self.stack = QStackedLayout(self)
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.addWidget(content)
        self.stack.addWidget(self.skeleton)
        self.stack.setCurrentIndex(0)

        self.set_thumbnail_size(thumbnail_size)
        self._refresh_visibility_style(self.status_combo.currentText())

    @property
    def is_visible_entry(self) -> bool:
        return self.status_combo.currentText() == "Visible"

    def set_placeholder(self, active: bool) -> None:
        self.stack.setCurrentIndex(1 if active else 0)
        self.setCursor(
            Qt.CursorShape.ClosedHandCursor if active else Qt.CursorShape.ArrowCursor
        )

    def export_payload(self, path: str) -> ImageCardPayload:
        return ImageCardPayload(
            path=path,
            filename=self.filename,
            visible=self.is_visible_entry,
            source_image=self.source_image,
            thumbnail_state=self.thumbnail_state,
        )

    def apply_payload(self, payload: ImageCardPayload, size: int) -> None:
        self.set_placeholder(False)
        self.filename = payload.filename
        self.source_image = payload.source_image
        self.thumbnail_state = payload.thumbnail_state
        self.name_label.setText(payload.filename)
        self.name_label.setToolTip(payload.filename)

        was_blocked = self.status_combo.blockSignals(True)
        self.status_combo.setCurrentText("Visible" if payload.visible else "Hidden")
        self.status_combo.blockSignals(was_blocked)
        self._refresh_visibility_style(self.status_combo.currentText())
        self._render_thumbnail(size)

    def set_thumbnail_size(self, size: int) -> None:
        card_size = item_card_size(size)
        self.setFixedSize(card_size)
        self.thumbnail_label.setFixedSize(size, size)
        self.name_label.setFixedWidth(card_size.width() - 24)
        self.name_label.setFixedHeight(38)
        self.status_combo.setFixedWidth(card_size.width() - 20)
        self.skeleton.set_thumbnail_size(size)
        self._render_thumbnail(size)

    def set_thumbnail(self, image: QImage | None, size: int) -> None:
        if image is not None and not image.isNull():
            self.source_image = image
            self.thumbnail_state = "ready"
        else:
            self.source_image = None
            self.thumbnail_state = "unavailable"
        self._render_thumbnail(size)

    def _render_thumbnail(self, size: int) -> None:
        self.thumbnail_label.clear()
        if self.thumbnail_state == "unavailable":
            self.thumbnail_label.setText("Unavailable")
            return
        if self.source_image is None:
            self.thumbnail_label.setText("Loading…")
            return

        pixmap = QPixmap.fromImage(
            self.source_image.scaled(
                size,
                size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        self.thumbnail_label.setPixmap(pixmap)

    def show_unavailable(self) -> None:
        self.source_image = None
        self.thumbnail_state = "unavailable"
        self._render_thumbnail(self.thumbnail_label.width())

    @Slot(str)
    def _refresh_visibility_style(self, text: str) -> None:
        state = text.casefold()
        self.status_combo.setProperty("visibilityState", state)
        style = self.status_combo.style()
        style.unpolish(self.status_combo)
        style.polish(self.status_combo)
        self.status_combo.update()


@dataclass
class DragState:
    payload: ImageCardPayload
    origin_row: int
    placeholder_row: int
    start_pos: QPoint
    hotspot: QPoint
    preview: QLabel
    current_pos: QPoint


class ImageGrid(QListWidget):
    order_changed = Signal()

    AUTO_SCROLL_MARGIN = 52
    AUTO_SCROLL_INTERVAL_MS = 14

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("imageGrid")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setMovement(QListView.Movement.Static)
        self.setDragDropMode(QListView.DragDropMode.NoDragDrop)
        self.setDragEnabled(False)
        self.setAcceptDrops(False)
        self.setDropIndicatorShown(False)
        self.setWrapping(True)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setSpacing(0)
        self.setUniformItemSizes(True)
        self.setSelectionMode(QListView.SelectionMode.SingleSelection)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setViewportMargins(0, 4, 0, 4)

        self._thumbnail_size = DEFAULT_THUMBNAIL_SIZE
        self._pressed_item: QListWidgetItem | None = None
        self._press_pos: QPoint | None = None
        self._press_hotspot = QPoint()
        self._drag: DragState | None = None

        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(self.AUTO_SCROLL_INTERVAL_MS)
        self._auto_scroll_timer.timeout.connect(self._auto_scroll_tick)

    @property
    def dragging(self) -> bool:
        return self._drag is not None

    def set_thumbnail_size(self, size: int) -> None:
        if self.dragging:
            self.cancel_drag()

        self._thumbnail_size = size
        self.setIconSize(QSize(size, size))
        self.setGridSize(item_grid_size(size))

        card_size = item_card_size(size)
        for row in range(self.count()):
            item = self.item(row)
            if item is None:
                continue
            item.setSizeHint(card_size)
            widget = self.itemWidget(item)
            if widget is not None:
                cast(ImageItemWidget, widget).set_thumbnail_size(size)

        self.scheduleDelayedItemsLayout()

    def add_image_item(self, item: QListWidgetItem, widget: ImageItemWidget) -> None:
        item.setSizeHint(item_card_size(self._thumbnail_size))
        self.addItem(item)
        self.setItemWidget(item, widget)

    def update_thumbnail(self, filename: str, image: QImage | None) -> bool:
        drag = self._drag
        if drag is not None and drag.payload.filename == filename:
            state = (
                "ready" if image is not None and not image.isNull() else "unavailable"
            )
            drag.payload = replace(
                drag.payload,
                source_image=image if state == "ready" else None,
                thumbnail_state=state,
            )
            return True

        for row in range(self.count()):
            widget = self._widget_at(row)
            if widget is not None and widget.filename == filename:
                widget.set_thumbnail(image, self._thumbnail_size)
                return True
        return False

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return

        super().mousePressEvent(event)
        pos = event.position().toPoint()
        item = self.itemAt(pos)

        self._pressed_item = item
        self._press_pos = pos if item is not None else None
        if item is not None:
            item_rect = self.visualItemRect(item)
            self._press_hotspot = pos - item_rect.topLeft()
        else:
            self._press_hotspot = QPoint()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = event.position().toPoint()

        if self._drag is not None:
            self._update_drag(pos)
            event.accept()
            return

        if (
            self._pressed_item is None
            or self._press_pos is None
            or not event.buttons() & Qt.MouseButton.LeftButton
        ):
            super().mouseMoveEvent(event)
            return

        drag_distance = (pos - self._press_pos).manhattanLength()
        if drag_distance < QApplication.startDragDistance():
            super().mouseMoveEvent(event)
            return

        if self._begin_drag(pos):
            self._update_drag(pos)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._drag is not None:
            self._update_drag(event.position().toPoint())
            self._finish_drag(commit=True)
            event.accept()
            return

        self._clear_press_state()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape and self._drag is not None:
            self.cancel_drag()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        if self._drag is not None:
            self.cancel_drag()
        super().focusOutEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._drag is not None:
            event.accept()
            return

        scroll_bar = self.verticalScrollBar()
        angle = event.angleDelta().y()
        if angle == 0:
            super().wheelEvent(event)
            return

        pixels = max(1, abs(angle) // 6)
        sign = -1 if angle > 0 else 1
        current = scroll_bar.value()
        target = max(
            scroll_bar.minimum(), min(scroll_bar.maximum(), current + sign * pixels)
        )
        scroll_bar.setValue(target)
        event.accept()

    def cancel_drag(self) -> None:
        self._finish_drag(commit=False)

    def _widget_at(self, row: int) -> ImageItemWidget | None:
        item = self.item(row)
        if item is None:
            return None
        widget = self.itemWidget(item)
        return cast(ImageItemWidget, widget) if widget is not None else None

    def _payload_at(self, row: int) -> ImageCardPayload | None:
        item = self.item(row)
        widget = self._widget_at(row)
        if item is None or widget is None:
            return None
        return widget.export_payload(str(item.data(Qt.ItemDataRole.UserRole) or ""))

    def _apply_payload(self, row: int, payload: ImageCardPayload) -> None:
        item = self.item(row)
        widget = self._widget_at(row)
        if item is None or widget is None:
            return
        item.setData(Qt.ItemDataRole.UserRole, payload.path)
        item.setToolTip(payload.filename)
        widget.apply_payload(payload, self._thumbnail_size)

    def _begin_drag(self, current_pos: QPoint) -> bool:
        item = self._pressed_item
        start_pos = self._press_pos
        if item is None or start_pos is None:
            return False

        origin_row = self.row(item)
        widget = self._widget_at(origin_row)
        payload = self._payload_at(origin_row)
        if origin_row < 0 or widget is None or payload is None:
            self._clear_press_state()
            return False

        snapshot = widget.grab()
        preview = QLabel(self.viewport())
        preview.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        preview.setPixmap(snapshot)
        preview.setFixedSize(widget.size())
        preview.setScaledContents(True)

        opacity = QGraphicsOpacityEffect(preview)
        opacity.setOpacity(0.88)
        preview.setGraphicsEffect(opacity)
        preview.show()
        preview.raise_()

        widget.set_placeholder(True)
        self._drag = DragState(
            payload=payload,
            origin_row=origin_row,
            placeholder_row=origin_row,
            start_pos=start_pos,
            hotspot=self._press_hotspot,
            preview=preview,
            current_pos=current_pos,
        )

        self.setCurrentRow(origin_row)
        self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
        self.viewport().grabMouse()
        self._auto_scroll_timer.start()
        return True

    def _update_drag(self, pos: QPoint) -> None:
        drag = self._drag
        if drag is None:
            return

        drag.current_pos = pos
        drag.preview.move(pos - drag.hotspot)
        drag.preview.raise_()

        target_row = self._target_row_at(pos)
        if target_row is not None:
            self._move_placeholder(target_row)

    def _target_row_at(self, pos: QPoint) -> int | None:
        drag = self._drag
        if drag is None or self.count() == 0:
            return None

        index = self.indexAt(pos)
        if index.isValid():
            return index.row()

        nearest_row: int | None = None
        nearest_distance: int | None = None
        for row in range(self.count()):
            item = self.item(row)
            if item is None:
                continue
            rect = self.visualItemRect(item)
            if not rect.isValid():
                continue

            dx = max(rect.left() - pos.x(), 0, pos.x() - rect.right())
            dy = max(rect.top() - pos.y(), 0, pos.y() - rect.bottom())
            distance = dx * dx + dy * dy
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_row = row

        return nearest_row if nearest_row is not None else drag.placeholder_row

    def _move_placeholder(self, target_row: int) -> None:
        drag = self._drag
        if drag is None:
            return

        current_row = drag.placeholder_row
        target_row = max(0, min(target_row, self.count() - 1))
        if target_row == current_row:
            return

        if target_row > current_row:
            for row in range(current_row, target_row):
                payload = self._payload_at(row + 1)
                if payload is not None:
                    self._apply_payload(row, payload)
        else:
            for row in range(current_row, target_row, -1):
                payload = self._payload_at(row - 1)
                if payload is not None:
                    self._apply_payload(row, payload)

        placeholder_widget = self._widget_at(target_row)
        if placeholder_widget is not None:
            placeholder_widget.set_placeholder(True)
        drag.placeholder_row = target_row
        self.setCurrentRow(target_row)
        self.viewport().update()

    def _auto_scroll_tick(self) -> None:
        drag = self._drag
        if drag is None:
            return

        viewport_height = self.viewport().height()
        y = drag.current_pos.y()
        margin = min(self.AUTO_SCROLL_MARGIN, max(24, viewport_height // 4))
        delta = 0

        if y < margin:
            strength = (margin - y) / margin
            delta = -max(4, int(22 * strength))
        elif y > viewport_height - margin:
            strength = (y - (viewport_height - margin)) / margin
            delta = max(4, int(22 * strength))

        if delta == 0:
            return

        scroll_bar = self.verticalScrollBar()
        old_value = scroll_bar.value()
        scroll_bar.setValue(old_value + delta)
        if scroll_bar.value() != old_value:
            self._update_drag(drag.current_pos)

    def _finish_drag(self, commit: bool) -> None:
        drag = self._drag
        if drag is None:
            self._clear_press_state()
            return

        self._auto_scroll_timer.stop()

        if not commit:
            self._move_placeholder(drag.origin_row)

        final_row = drag.placeholder_row
        self._apply_payload(final_row, drag.payload)

        final_widget = self._widget_at(final_row)
        if final_widget is not None:
            # Put the floating preview exactly over the destination before hiding
            # it, so release visually resolves into the final card rather than
            # disappearing at the cursor position.
            drag.preview.setGeometry(final_widget.geometry())
            final_widget.set_placeholder(False)

        drag.preview.hide()
        drag.preview.deleteLater()

        if QWidget.mouseGrabber() is self.viewport():
            self.viewport().releaseMouse()
        self.viewport().unsetCursor()

        changed = commit and final_row != drag.origin_row
        self._drag = None
        self._clear_press_state()
        self.viewport().update()

        if changed:
            self.order_changed.emit()

    def _clear_press_state(self) -> None:
        self._pressed_item = None
        self._press_pos = None
        self._press_hotspot = QPoint()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Image Order Manager")
        self.resize(1180, 800)
        self.setMinimumSize(760, 560)

        self.current_directory: Path | None = None
        self.thumbnail_size = DEFAULT_THUMBNAIL_SIZE
        self.load_generation = 0

        self.thread_pool = QThreadPool(self)
        ideal_threads = QThreadPool.globalInstance().maxThreadCount() or 4
        self.thread_pool.setMaxThreadCount(max(2, ideal_threads - 1))

        title_label = QLabel("Image Order Manager")
        title_label.setObjectName("titleLabel")

        subtitle_label = QLabel(
            "Drag a card to reorder it. The placeholder shows exactly where it will land."
        )
        subtitle_label.setObjectName("subtitleLabel")

        self.path_label = QLabel("No folder selected")
        self.path_label.setObjectName("pathLabel")
        self.path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        self.pick_button = QPushButton("Choose folder")
        self.pick_button.clicked.connect(self.choose_directory)

        self.save_button = QPushButton("Save order")
        self.save_button.setObjectName("primaryButton")
        self.save_button.setEnabled(False)
        self.save_button.clicked.connect(self.save_order)

        self.preview_slider = QSlider(Qt.Orientation.Horizontal)
        self.preview_slider.setRange(MIN_THUMBNAIL_SIZE, MAX_THUMBNAIL_SIZE)
        self.preview_slider.setValue(self.thumbnail_size)
        self.preview_slider.valueChanged.connect(self.handle_preview_size_changed)

        self.preview_label = QLabel(f"Thumbnail size: {self.thumbnail_size}px")
        self.preview_label.setObjectName("previewLabel")

        self.grid = ImageGrid()
        self.grid.order_changed.connect(self.refresh_status)

        toolbar = QFrame()
        toolbar.setObjectName("toolbarCard")
        toolbar_layout = QGridLayout(toolbar)
        toolbar_layout.setContentsMargins(18, 16, 18, 16)
        toolbar_layout.setHorizontalSpacing(12)
        toolbar_layout.setVerticalSpacing(10)
        toolbar_layout.addWidget(title_label, 0, 0, 1, 2)
        toolbar_layout.addWidget(subtitle_label, 1, 0, 1, 2)
        toolbar_layout.addWidget(self.pick_button, 0, 2)
        toolbar_layout.addWidget(self.save_button, 0, 3)
        toolbar_layout.addWidget(self.path_label, 2, 0, 1, 4)
        toolbar_layout.addWidget(self.preview_label, 3, 0)
        toolbar_layout.addWidget(self.preview_slider, 3, 1, 1, 3)
        toolbar_layout.setColumnStretch(1, 1)

        self.status_label = QLabel("Choose a folder containing images to begin.")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)

        status_card = QFrame()
        status_card.setObjectName("statusCard")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(14, 10, 14, 10)
        status_layout.addWidget(self.status_label)

        root = QWidget()
        root.setObjectName("windowRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(12)
        root_layout.addWidget(toolbar)
        root_layout.addWidget(self.grid, 1)
        root_layout.addWidget(status_card)
        self.setCentralWidget(root)

        self.grid.set_thumbnail_size(self.thumbnail_size)

        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("Ctrl+R")
        refresh_action.triggered.connect(self.refresh_directory)
        self.addAction(refresh_action)

        save_action = QAction("Save", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_order)
        self.addAction(save_action)

    def handle_preview_size_changed(self, value: int) -> None:
        self.thumbnail_size = max(
            MIN_THUMBNAIL_SIZE,
            min(value, MAX_THUMBNAIL_SIZE),
        )
        self.preview_label.setText(f"Thumbnail size: {self.thumbnail_size}px")
        self.grid.set_thumbnail_size(self.thumbnail_size)

    def choose_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select an image folder",
            str(self.current_directory or QDir.homePath()),
        )
        if directory:
            self.load_directory(Path(directory))

    def refresh_directory(self) -> None:
        if self.current_directory is not None:
            self.load_directory(self.current_directory)

    def load_directory(self, directory: Path) -> None:
        self.grid.cancel_drag()
        self.current_directory = directory
        self.path_label.setText(str(directory))

        self.load_generation += 1
        generation = self.load_generation
        self.thread_pool.clear()
        self.grid.clear()

        try:
            images = load_images(directory)
        except OSError as exc:
            self.status_label.setText(f"Could not read this folder: {exc}")
            self.save_button.setEnabled(False)
            return

        images = parse_instruction_order(directory, images)
        # images = apply_saved_visibility(directory, images)

        if not images:
            self.status_label.setText("No supported images were found in this folder.")
            self.save_button.setEnabled(False)
            return

        self.status_label.setText(f"Loading {len(images)} images…")
        self.save_button.setEnabled(True)

        for entry in images:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, str(entry.path))
            item.setToolTip(entry.filename)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            widget = ImageItemWidget(
                entry.filename,
                entry.visible,
                self.thumbnail_size,
            )
            widget.status_combo.currentTextChanged.connect(self.refresh_status)
            self.grid.add_image_item(item, widget)

            task = ThumbnailTask(entry.path, generation)
            task.signals.loaded.connect(self.handle_thumbnail_loaded)
            self.thread_pool.start(task)

        self.refresh_status()

    @Slot(int, str, object)
    def handle_thumbnail_loaded(
        self,
        generation: int,
        filename: str,
        image: object,
    ) -> None:
        if generation != self.load_generation:
            return

        loaded_image = (
            image if isinstance(image, QImage) and not image.isNull() else None
        )
        self.grid.update_thumbnail(filename, loaded_image)

    @Slot()
    def refresh_status(self, *_: object) -> None:
        total = self.grid.count()
        visible = sum(
            1
            for row in range(total)
            if (
                (item := self.grid.item(row)) is not None
                and (widget := self.grid.itemWidget(item)) is not None
                and cast(ImageItemWidget, widget).is_visible_entry
            )
        )
        hidden = total - visible
        self.status_label.setText(
            f"{total} image{'s' if total != 1 else ''} · "
            f"{visible} visible · {hidden} hidden · "
            "Drag anywhere on an image card to reorder it; press Esc to cancel a drag."
        )

    def ordered_entries(self) -> list[tuple[str, str]]:
        ordered: list[tuple[str, str]] = []
        for row in range(self.grid.count()):
            item = self.grid.item(row)
            if item is None:
                continue
            widget = self.grid.itemWidget(item)
            if widget is None:
                continue
            image_widget = cast(ImageItemWidget, widget)
            status = "visible" if image_widget.is_visible_entry else "hidden"
            ordered.append((image_widget.filename, status))
        return ordered

    def save_order(self) -> None:
        self.grid.cancel_drag()
        if self.current_directory is None:
            QMessageBox.information(
                self, "No folder selected", "Choose a folder first."
            )
            return

        entries = self.ordered_entries()
        if not entries:
            QMessageBox.information(
                self, "Nothing to save", "Load images before saving."
            )
            return

        visible_names = [name for name, status in entries if status == "visible"]

        instructions_path = self.current_directory / INSTRUCTIONS_FILENAME

        try:
            write_text_atomic(
                instructions_path,
                "\n".join(visible_names) + "\n",
            )
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Save failed",
                f"Could not save the visible image list:\n{exc}",
            )
            return

        self.status_label.setText(
            f"Saved {len(visible_names)} visible filenames to {INSTRUCTIONS_FILENAME}."
        )
        QMessageBox.information(
            self,
            "Saved",
            f"Saved the visible image order to:\n{instructions_path}",
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.grid.cancel_drag()
        self.thread_pool.clear()
        self.thread_pool.waitForDone(1500)
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Image Order Manager")
    app.setStyleSheet(APP_STYLE)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
