# Phase 1 — UI Modularization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Break the ~1170-line `gui/main_window.py` monolith into a page-registry shell plus focused page / widget / service modules, with **zero behaviour or visual change**, so new pages/features are easy to add.

**Architecture:** `MainWindow` becomes a thin shell that builds the sidebar from a `navigation.py` registry and drives a `QStackedWidget`. Each page is a `BasePage(QWidget)`. The relist page's banner, prompt panel and form helpers become reusable widgets; its settings persistence and image validation become injectable services. Extracted pure logic (image validation, settings) gets unit tests.

**Tech Stack:** Python 3.14, PySide6, pytest (offscreen Qt via `QT_QPA_PLATFORM=offscreen`).

**Interpreter/test commands (Windows):**
- Python: `.venv/Scripts/python.exe`
- Tests: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -m pytest tests/ -q`
- Smoke: `QT_QPA_PLATFORM=offscreen .venv/Scripts/python.exe -c "from relister.gui.main_window import MainWindow; from PySide6.QtWidgets import QApplication; a=QApplication([]); w=MainWindow(); w.show(); print('ok')"`

---

## File structure (Phase 1)

```
gui/
  services/
    __init__.py
    settings_service.py   # NEW  SettingsService — typed QSettings wrapper
    images_validator.py   # NEW  validate_images_directory() -> ValidationResult (pure)
  widgets/
    __init__.py
    form_helpers.py       # NEW  section_row(), field_label()
    top_banner.py         # NEW  TopBanner(QFrame)
    prompt_panel.py       # NEW  PromptPanel(QFrame) — emits submitted(str)
  pages/
    __init__.py
    base_page.py          # NEW  BasePage(QWidget): nav_label, on_activated()
    relist_page.py        # NEW  RelistPage(BasePage) — relist form + worker lifecycle
    image_page.py         # NEW  ImagePage(BasePage) — wraps ImageOrderPage
  navigation.py           # NEW  NavItem + build_nav_items()
  main_window.py          # REWRITE  slim shell
  app.py                  # MODIFY  (wire services if needed)
  logging_handler.py prompt_bridge.py relist_worker.py theme.py  # unchanged
tests/gui/
  test_images_validator.py     # NEW
  test_settings_service.py     # NEW
  test_relist_page_status_feedback.py  # MOVED from test_main_window_status_feedback.py
```

---

### Task 1: SettingsService

**Files:** Create `src/relister/gui/services/__init__.py`, `src/relister/gui/services/settings_service.py`; Test `tests/gui/test_settings_service.py`.

- [ ] **Step 1: Failing test**
```python
# tests/gui/test_settings_service.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QSettings
from relister.gui.services.settings_service import SettingsService

def _svc():
    s = QSettings("RelisterTest", f"unit-{os.getpid()}")
    s.clear()
    return SettingsService(s)

def test_bool_coercion_from_string():
    svc = _svc()
    svc.set_value("publish", "true")
    assert svc.bool_value("publish", False) is True
    assert svc.bool_value("missing", True) is True

def test_str_roundtrip_and_default():
    svc = _svc()
    svc.set_value("source", "zoopla")
    assert svc.value("source", "x") == "zoopla"
    assert svc.value("missing", "fallback") == "fallback"
```
- [ ] **Step 2: Run — expect fail** `... -m pytest tests/gui/test_settings_service.py -q` → ModuleNotFound.
- [ ] **Step 3: Implement**
```python
# src/relister/gui/services/settings_service.py
from __future__ import annotations
from typing import Any
from PySide6.QtCore import QSettings

class SettingsService:
    """Typed wrapper over QSettings; centralizes bool coercion."""
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

    def geometry(self):
        return self._s.value("window_geometry")

    def set_geometry(self, data) -> None:
        self._s.setValue("window_geometry", data)
```
- [ ] **Step 4: Run — expect pass.**
- [ ] **Step 5: Commit** `git add -A && git commit -m "feat(gui): add SettingsService"`

---

### Task 2: ImagesValidator (pure extraction of `_validate_images_directory`)

**Files:** Create `src/relister/gui/services/images_validator.py`; Test `tests/gui/test_images_validator.py`.

The current `_validate_images_directory` (main_window.py:715-819) mixes rendering with logic. Extract the decision logic into a pure function returning a `ValidationResult`. States mirror the original: `neutral` (empty → ready), `error` (missing dir / unreadable), `warning` (no images / missing/empty/invalid instructions), `success` (ready). `action_visible` mirrors the original flag.

- [ ] **Step 1: Failing test**
```python
# tests/gui/test_images_validator.py
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
from PIL import Image  # via image_manager's stack if present; else write raw bytes
from relister.gui.services.images_validator import validate_images_directory
from image_manager.image_manager_app import INSTRUCTIONS_FILENAME

def _img(p: Path):
    # minimal valid-looking file with a supported extension
    p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 64)

def test_empty_text_is_neutral_ready():
    r = validate_images_directory("")
    assert r.state == "neutral" and r.ready is True

def test_missing_directory_is_error(tmp_path):
    r = validate_images_directory(str(tmp_path / "nope"))
    assert r.state == "error" and r.ready is False

def test_missing_instructions_is_warning(tmp_path):
    _img(tmp_path / "a.png")
    r = validate_images_directory(str(tmp_path))
    assert r.state == "warning" and r.ready is False and r.action_visible is True

def test_valid_folder_is_success(tmp_path):
    _img(tmp_path / "a.png")
    (tmp_path / INSTRUCTIONS_FILENAME).write_text("a.png\n", encoding="utf-8")
    r = validate_images_directory(str(tmp_path))
    assert r.state == "success" and r.ready is True
```
(If `is_supported_image` rejects the fake PNG, the test writes a real image via PIL — check `image_manager` deps; adjust `_img` to whatever `is_supported_image` accepts.)
- [ ] **Step 2: Run — expect fail.**
- [ ] **Step 3: Implement** `validate_images_directory(images_text)` porting the branch logic verbatim from main_window.py:715-819, returning `ValidationResult(state, message, ready, action_visible)` instead of calling `_set_image_status`/`_update_start_state`. Keep the exact messages.
```python
# src/relister/gui/services/images_validator.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from image_manager.image_manager_app import (
    INSTRUCTIONS_FILENAME, is_supported_image, load_images,
)

@dataclass(frozen=True)
class ValidationResult:
    state: str        # neutral | success | warning | error
    message: str
    ready: bool
    action_visible: bool = False

def validate_images_directory(images_text: str) -> ValidationResult:
    images_text = images_text.strip()
    if not images_text:
        return ValidationResult("neutral",
            "No replacement image folder selected. Existing scraped images will be used.",
            True)
    images_path = Path(images_text)
    if not images_path.is_dir():
        return ValidationResult("error",
            "The selected image folder does not exist. Choose a different folder.", False)
    try:
        images = load_images(images_path)
    except OSError as exc:
        return ValidationResult("error",
            f"The selected image folder could not be read: {exc}", False)
    if not images:
        return ValidationResult("warning",
            "No supported images were found in this folder. Select a different folder.", False)
    instructions_path = images_path / INSTRUCTIONS_FILENAME
    if not instructions_path.is_file():
        return ValidationResult("warning",
            f"{INSTRUCTIONS_FILENAME} is missing. Run the image organiser before continuing.",
            False, True)
    try:
        ordered = [l.strip() for l in
                   instructions_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError as exc:
        return ValidationResult("error",
            f"{INSTRUCTIONS_FILENAME} could not be read: {exc}", False, True)
    if not ordered:
        return ValidationResult("warning",
            f"{INSTRUCTIONS_FILENAME} is empty. Open the image organiser and save at least one visible image.",
            False, True)
    missing = [n for n in ordered if not is_supported_image(images_path / n)]
    if missing:
        preview = ", ".join(missing[:3]); suffix = "…" if len(missing) > 3 else ""
        return ValidationResult("warning",
            f"The saved order refers to missing or unsupported files: {preview}{suffix}. Re-save the image order.",
            False, True)
    n = len(ordered)
    return ValidationResult("success",
        f"Image folder ready: {n} image{'s' if n != 1 else ''} will be uploaded in the saved order.",
        True)
```
- [ ] **Step 4: Run — expect pass** (fix `_img` if `is_supported_image` needs a real image).
- [ ] **Step 5: Commit** `git commit -am "feat(gui): extract pure images validator"`

---

### Task 3: Widgets — form_helpers, TopBanner, PromptPanel

**Files:** Create `src/relister/gui/widgets/__init__.py`, `form_helpers.py`, `top_banner.py`, `prompt_panel.py`.

- [ ] **Step 1:** `form_helpers.py` — move `_section_row` (main_window.py:536-547) → `section_row(tag_text, content_layout)` and `_field_label` (549-553) → `field_label(text)` as module functions (same object names `groupLabel`, `fieldLabel`).
- [ ] **Step 2:** `top_banner.py` — `TopBanner(QFrame)` encapsulating `_build_top_banner`, `_position_top_banner`, `_show_top_banner`, `_hide_top_banner`, `_finish_banner_animation` (main_window.py:424-479, 837-875). Public API: `show_banner(state, message)`, `hide_banner()`, `reposition()`. Keeps object names `topBanner`/`topBannerIcon`/`topBannerText`/`topBannerClose`. Parent = the page; it raises itself.
- [ ] **Step 3:** `prompt_panel.py` — `PromptPanel(QFrame)` encapsulating `_build_input_section`, `_set_prompt_active`, `_show_prompt`(UI parts), `_clear_prompt`, `_submit_prompt`(UI parts) (main_window.py:481-534, 1060-1125). Signals: `submitted = Signal(str)`. Public API: `show_prompt(prompt, sensitive)`, `clear()`, `set_active(bool)`. Emits `submitted` on Enter/click; the page owns the prompt_bridge wiring and attention (raise/focus/beep).
- [ ] **Step 4: Smoke** import each widget module (offscreen) → no error.
- [ ] **Step 5: Commit** `git commit -am "feat(gui): extract form helpers, TopBanner, PromptPanel widgets"`

---

### Task 4: BasePage + ImagePage

**Files:** Create `src/relister/gui/pages/__init__.py`, `base_page.py`, `image_page.py`.

- [ ] **Step 1:** `base_page.py`
```python
# src/relister/gui/pages/base_page.py
from __future__ import annotations
from PySide6.QtWidgets import QWidget

class BasePage(QWidget):
    nav_label: str = ""
    def on_activated(self) -> None:  # called when page becomes visible
        return None
```
- [ ] **Step 2:** `image_page.py` — `ImagePage(BasePage)` composing `ImageOrderPage`, `nav_label = "Image organiser"`. Forwards `instructions_saved`, `directory_changed`, and methods `load_directory`, `choose_directory`, `shutdown`. Layout: single `QVBoxLayout` holding the `ImageOrderPage`.
- [ ] **Step 3: Smoke** import + instantiate offscreen.
- [ ] **Step 4: Commit** `git commit -am "feat(gui): add BasePage and ImagePage adapter"`

---

### Task 5: RelistPage

**Files:** Create `src/relister/gui/pages/relist_page.py`.

Move all relist-page construction and logic out of `MainWindow`: `_build_relist_page`, `_create_provider_combo`, provider constants, image browse/validate/organiser handoff, `_build_request`, worker lifecycle (`_start_relist`, `_cancel_relist`, `_on_success/_failure/_cancelled/_worker_done/_thread_finished`, `_set_running`, `_update_start_state`), log append/clear, and settings restore/save for its own fields. Constructor:

```python
class RelistPage(BasePage):
    nav_label = "Relist property"
    request_organiser = Signal(object)     # Path | None -> ask shell to open organiser
    def __init__(self, settings: SettingsService, prompt_bridge: PromptBridge,
                 log_handler, parent=None): ...
```

- Uses `TopBanner`, `PromptPanel`, `section_row`/`field_label`.
- Image validation calls `validate_images_directory(text)` then renders (`_apply_validation_result`) — replaces the inline `_validate_images_directory`; keeps `image_status_label` + `_images_ready` + Start gating.
- `set_images_dir(path)` public method for the shell to push a folder in after organiser save.
- Keep every object name and signal used elsewhere.
- The cross-page organiser handoff (`_open_selected_images_in_organizer`, `_open_organizer_from_navigation`) is split: RelistPage emits `request_organiser(images_path_or_None)`; the shell opens the ImagePage.

- [ ] **Step 1:** Implement `RelistPage` by relocating the code (preserve names/signals).
- [ ] **Step 2: Smoke** `from relister.gui.pages.relist_page import RelistPage` offscreen + instantiate with a `SettingsService()` and `PromptBridge()`.
- [ ] **Step 3: Commit** `git commit -am "feat(gui): extract RelistPage"`

---

### Task 6: navigation.py + slim MainWindow

**Files:** Create `src/relister/gui/navigation.py`; Rewrite `src/relister/gui/main_window.py`.

- [ ] **Step 1:** `navigation.py`
```python
# src/relister/gui/navigation.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from .pages.base_page import BasePage

@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    factory: Callable[[], BasePage]
```
- [ ] **Step 2:** Rewrite `MainWindow`: build sidebar (brand + WORKSPACE + nav buttons from the registry), a `QStackedWidget`, install log handler, construct pages via factories, wire nav buttons → `setCurrentIndex` + `page.on_activated()`, connect `RelistPage.request_organiser` → open ImagePage + `image_page.load_directory`, connect `image_page.instructions_saved` → `relist_page.set_images_dir` + switch back, keep `closeEvent` (running-guard + `image_page.shutdown()` + remove log handler) and geometry restore/save via `SettingsService`. Keep `appRoot`/`sidebar`/`pageStack`/`navButton` object names + stylesheet.
- [ ] **Step 3: Run full suite + smoke.**
- [ ] **Step 4: Commit** `git commit -am "refactor(gui): slim MainWindow to page-registry shell"`

---

### Task 7: Migrate the existing GUI test

**Files:** Rename `tests/gui/test_main_window_status_feedback.py` → `tests/gui/test_relist_page_status_feedback.py`; retarget at `RelistPage`.

- [ ] **Step 1:** Point the `window` fixture at `MainWindow` but assert against `window.relist_page.top_banner` / `window.relist_page.image_status_label`, or construct `RelistPage` directly. Preserve the three behaviours (inline status neutral-hides, warning/error states, banner overlay+close).
- [ ] **Step 2: Run** `... -m pytest tests/ -q` → all pass.
- [ ] **Step 3: Commit** `git commit -am "test(gui): retarget status-feedback tests at RelistPage"`

---

## Self-review checkpoints
- Behaviour parity: providers, URL, images (browse/organise/validate), options, start/cancel, publish confirm, banner, prompt attention (raise/focus/beep/alert), settings persistence keys unchanged.
- Object names preserved so `theme.build_stylesheet()` still matches every widget.
- No new deps in Phase 1.
