from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal


class LogEmitter(QObject):
    message_emitted = Signal(str)


class QtLogHandler(logging.Handler):
    """Logging handler that forwards formatted records to a Qt signal."""

    def __init__(self, emitter: LogEmitter) -> None:
        super().__init__()
        self._emitter = emitter

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self._emitter.message_emitted.emit(message)
        except Exception:
            self.handleError(record)
