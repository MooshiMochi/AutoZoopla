from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings


class SettingsService:
    """Typed wrapper over ``QSettings``; centralizes bool coercion.

    All GUI settings access goes through this service so the storage backend
    and the string/bool coercion rules live in one place.
    """

    def __init__(self, settings: QSettings | None = None) -> None:
        self._s = settings or QSettings("Relister", "RelisterDesktop")

    def value(self, key: str, default: str = "") -> str:
        return str(self._s.value(key, default))

    def bool_value(self, key: str, default: bool = False) -> bool:
        raw = self._s.value(key, default)
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() in {"1", "true", "yes"}

    def set_value(self, key: str, value: Any) -> None:
        self._s.setValue(key, value)

    def geometry(self) -> Any:
        return self._s.value("window_geometry")

    def set_geometry(self, data: Any) -> None:
        self._s.setValue("window_geometry", data)
