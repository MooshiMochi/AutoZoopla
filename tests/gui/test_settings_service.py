import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings

from relister.gui.services.settings_service import SettingsService


def _svc() -> SettingsService:
    settings = QSettings("RelisterTest", f"unit-{os.getpid()}")
    settings.clear()
    return SettingsService(settings)


def test_bool_coercion_from_string():
    svc = _svc()
    svc.set_value("publish", "true")
    assert svc.bool_value("publish", False) is True
    assert svc.bool_value("missing", True) is True


def test_bool_coercion_from_native_bool():
    svc = _svc()
    svc.set_value("headless", True)
    assert svc.bool_value("headless", False) is True


def test_str_roundtrip_and_default():
    svc = _svc()
    svc.set_value("source", "zoopla")
    assert svc.value("source", "x") == "zoopla"
    assert svc.value("missing", "fallback") == "fallback"
