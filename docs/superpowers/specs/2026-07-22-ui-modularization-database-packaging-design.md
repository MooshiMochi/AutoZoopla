# AutoZoopla — UI modularization, database integration & Mac packaging — design

- **Date:** 2026-07-22
- **Status:** Approved (design signed off; spec under review)
- **Scope:** Three related but independently shippable subsystems:
  1. Modularize the PySide6 UI (pages + widgets + services) so pages/features are easy to add.
  2. Integrate a SQLite database mapping a listing ID → images folder, with prefill on
     URL paste, save on Start, and old→new ID migration on relist.
  3. Prepare the project to be bundled as a macOS app with a Sparkle auto-updater,
     built on a GitHub Actions macOS runner.

## Problem / motivation

- `gui/main_window.py` is a single ~1170-line class handling the sidebar, every page's
  widgets, image validation (~100 lines), settings persistence, and worker lifecycle.
  Adding a page or feature means editing this monolith. There is no page abstraction —
  the two pages (`RelistPage`, `ImageOrderPage`) are hardcoded into a `QStackedWidget`.
- Nothing durable is stored except `QSettings`. `storage/sqlite.py` is empty. The user
  re-selects the images folder for a property every time, and after a relist (which
  changes the listing ID) any association would be lost.
- The project has entry points but no bundler config, no updater, and hardcodes a
  relative `data/browser_states` path and a single browser — all of which break once
  bundled and shipped to a Mac.

## Non-goals

- No change to scraping/relisting/worker business logic beyond: (a) browser selection
  fallback, (b) routing the browser-state path through a shared resolver, (c) calling
  the DB repo at three points in `RelistPage`.
- No visual redesign — the 2026-07-21 redesign stands. Modularization preserves current
  appearance, object names, signals, settings keys, and behaviour.
- No Apple Developer account work performed blind: notarization/Developer-ID signing is
  scaffolded with documented secret placeholders, not fully wired.
- No heavy DB migration framework; `CREATE TABLE IF NOT EXISTS` + a `user_version` pragma.

---

## Subsystem 1 — UI modularization (pages + widgets + services)

### Target structure

```
gui/
  app.py                  # entry point: build services, window, updater; show()
  main_window.py          # slim shell: sidebar + QStackedWidget driven by the page registry
  navigation.py           # NavItem dataclass + PAGES registry; sidebar built from it
  pages/
    __init__.py
    base_page.py          # BasePage(QWidget)
    relist_page.py        # RelistPage: relist form, validation, worker lifecycle
    image_page.py         # adapter exposing ImageOrderPage as a BasePage
  widgets/
    __init__.py
    top_banner.py         # slide-down status banner (extracted from main_window)
    prompt_panel.py       # user-input panel + accent glow (extracted)
    form_helpers.py       # section_row(), field_label()
  services/
    __init__.py
    settings_service.py   # typed wrapper over QSettings
    images_validator.py   # pure validation → ValidationResult(state, message, ready)
  logging_handler.py  prompt_bridge.py  relist_worker.py  theme.py   # unchanged
```

### BasePage contract

```python
class BasePage(QWidget):
    nav_label: str                     # sidebar button text
    def on_activated(self) -> None: ...  # called when the page becomes visible (no-op default)
```

`ChevronCombo` / `ModernCheckBox` stay in `theme.py`.

### Page registry & shell

`navigation.py` holds an ordered list of `NavItem(key, label, factory)`. `MainWindow`:

- builds the sidebar buttons from the registry (same styling/object names as today),
- constructs each page via its factory, injecting shared services
  (`SettingsService`, `PropertyImagesRepo`, `ImagesValidator`),
- adds pages to the `QStackedWidget` and wires `nav_group` → `setCurrentIndex` +
  `page.on_activated()`.

Adding a page later = write a `BasePage` subclass + append one `NavItem`. `MainWindow`
drops from ~1170 lines to a thin shell (sidebar build, stack switch, close handling,
log handler install, updater kickoff).

### RelistPage

Owns everything currently under `_build_relist_page` and its helpers: the config card,
action bar, program-output card, the top banner (via `widgets/top_banner.py`), and the
prompt panel (via `widgets/prompt_panel.py`). It keeps its own worker/thread lifecycle
(`_start_relist`, `_cancel_relist`, success/failure/cancel slots) and emits nothing new.
Injected dependencies: `SettingsService`, `PropertyImagesRepo`, `ImagesValidator`,
and the source/destination provider keys (for ID extraction). All existing signal wiring,
attention behaviour (raise/focus/beep/alert), and settings keys are preserved.

### ImagePage

Thin adapter wrapping the existing `ImageOrderPage` from `image_manager`, exposing
`nav_label` and forwarding `instructions_saved` / `directory_changed` so `MainWindow`'s
current cross-page behaviour (load folder on nav, return-to-relist after save) is kept.

### Services

- `SettingsService`: typed getters/setters over `QSettings("Relister","RelisterDesktop")`
  for the existing keys (source, destination, listing_url, images_directory, publish,
  headless, verbose, window_geometry). Centralizes the `_as_bool` coercion.
- `ImagesValidator`: the current `_validate_images_directory` logic moved out of the
  widget into a pure function returning `ValidationResult(state: str, message: str,
  ready: bool)`. `RelistPage` renders the result (banner + Start-button gating). This
  makes the gnarliest logic unit-testable without a running UI.

---

## Subsystem 2 — Database integration

### Location & shared paths

New `core/paths.py` — a Qt-free app-data resolver used by GUI, CLI and browser session:

- macOS: `~/Library/Application Support/AutoZoopla/`
- Windows: `%LOCALAPPDATA%\AutoZoopla\`
- Linux: `~/.local/share/AutoZoopla/`

Exposes `data_dir()`, `database_path()` (`<data>/relister.db`),
`browser_states_dir()` (`<data>/browser_states`), `browser_cache_dir()`
(`<data>/ms-playwright`, overridable by `PLAYWRIGHT_BROWSERS_PATH`). No `QStandardPaths`
(it needs a running QApplication and isn't available to the CLI/session).

`browser/session.py` switches its hardcoded relative `data/browser_states` to
`paths.browser_states_dir()` so state survives bundling and a changing cwd.

### Storage package

```
storage/
  database.py         # connect(path) + init_schema(); resolves default path via core.paths
  property_images.py  # PropertyImagesRepo
```

Schema (deliberately minimal, extensible):

```sql
CREATE TABLE IF NOT EXISTS property_images (
    listing_id TEXT PRIMARY KEY,
    images_dir TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

`PropertyImagesRepo` (each method opens a short-lived `sqlite3` connection; all access
on the GUI thread):

- `get_images_dir(listing_id) -> str | None`
- `set_images_dir(listing_id, images_dir) -> None`  — upsert, stamps `updated_at`
- `migrate_id(old_id, new_id) -> None`  — moves the row old→new; if `new_id` already
  exists it is replaced (`INSERT OR REPLACE` / delete-then-update in a transaction)

### Provider-aware ID extraction

Add `@staticmethod extract_listing_id(url: str) -> str | None` to `PropertyProvider`,
with the Zoopla override reusing the existing
`url.rstrip("/").split("/")[-1].split("?")[0]` (from `create_listing_page.py`, which is
refactored to call the provider method). The DB layer stays provider-agnostic; a
`providers/factory.py` helper resolves a provider *class* by key for extraction without
needing credentials.

### Flow in RelistPage

1. **URL edited** → existing debounce → `id = provider.extract_listing_id(url)`.
   If `id` and `repo.get_images_dir(id)` returns a folder **and the images field is
   empty**, prefill it and show a subtle hint ("Loaded saved image folder for this
   listing."). Never clobbers a manually entered path.
2. **Start pressed** → after the request is built, if a real images folder is set:
   `repo.set_images_dir(id, images_dir)`. Saved regardless of dry-run/publish (per spec).
3. **Successful publish** (not dry-run, `result.destination_listing_url` present) →
   `old_id = provider.extract_listing_id(source_url)`,
   `new_id = provider.extract_listing_id(result.destination_listing_url)`,
   then `repo.migrate_id(old_id, new_id)`. Dry runs never migrate (no new listing).

Threading: the worker never touches SQLite. Lookup (URL edit) and migration
(`_on_success` slot) both run on the GUI thread, so short-lived connections are safe.

---

## Subsystem 3 — macOS packaging + Sparkle updater

### Browser strategy (Firefox preferred, WebKit fallback)

- **Runtime:** a `_launch_browser(playwright, headless)` helper in `session.py` tries
  `playwright.firefox.launch(...)`; if the Firefox executable is missing (launch raises),
  it falls back to `playwright.webkit.launch(...)`. Chromium is never required, so the
  large Chromium download is avoided entirely.
- **Distribution / install-time download:** the initial download ships as a **signed
  `.pkg`** whose `postinstall` script runs
  `playwright install firefox webkit` into a machine-wide
  `PLAYWRIGHT_BROWSERS_PATH=/Library/Application Support/AutoZoopla/ms-playwright`
  (world-readable; written as root at install). The app sets the same env var (via
  `core.paths.browser_cache_dir()`) **before** importing/launching Playwright.
- **Updates:** Sparkle ships app-only DMG/zip updates; the browsers already on disk
  persist across updates.
- **First-launch safety net:** on startup the app checks whether Firefox or WebKit is
  present; if neither is, it offers to download them with a progress dialog. Covers
  fresh DMG installs, CI hiccups, or a cleared cache.

### Bundler

**PyInstaller** (one-dir → `.app` → `.dmg`/`.pkg`). New `packaging/` dir:

- `AutoZoopla.spec` — PyInstaller spec (collects PySide6, Playwright's Python package;
  **not** the browser binaries).
- `Info.plist` — bundle id, version (from `relister.__version__`), and Sparkle keys
  `SUFeedURL`, `SUPublicEDKey`, `SUEnableAutomaticChecks`.
- `entitlements.plist` — hardened-runtime entitlements (placeholder for notarization).
- `make_dmg.sh`, `make_pkg.sh` (with `postinstall`) — build the DMG (updates) and the
  first-install PKG (browsers).

Version source of truth: `pyproject.toml` version, mirrored to a generated
`src/relister/__version__.py` (read via `importlib.metadata` at runtime with a fallback).

### Sparkle updater

New `gui/updater.py`:

- `SparkleUpdater` lazily loads `Sparkle.framework` through **pyobjc** and instantiates
  `SPUStandardUpdaterController`, which provides the standard **Install Update / Skip
  This Version / Remind Me Later** dialog for free.
- Platform-guarded: on non-macOS (Windows/Linux dev) it's a **no-op stub**, so the app
  runs unchanged during development. pyobjc is a macOS-only optional dependency.
- `MainWindow` calls `updater.start_background_checks()` on startup and exposes a
  "Check for Updates…" action.

Dependencies (`pyproject.toml`):

```toml
[project.optional-dependencies]
macos = ["pyobjc-core", "pyobjc-framework-Cocoa"]
build = ["pyinstaller"]
```

### CI — GitHub Actions (macOS runner)

`.github/workflows/release.yml`, triggered by a `v*` tag on `macos-latest`:

1. checkout, set up Python, `pip install .[build,macos]`
2. PyInstaller build → `.app`
3. `make_dmg.sh` (Sparkle update artifact) and `make_pkg.sh` (first-install artifact)
4. EdDSA-sign the DMG with Sparkle's `sign_update` (private key from
   `secrets.SPARKLE_PRIVATE_KEY`)
5. `generate_appcast` → update `appcast.xml`
6. attach DMG + PKG + `appcast.xml` to the GitHub Release; `SUFeedURL` points at the
   release-hosted `appcast.xml`

Apple Developer-ID signing + notarization steps are present but gated on
`secrets.APPLE_*` placeholders, documented in `packaging/README.md` with EdDSA
key-generation instructions.

---

## Sequencing (three phases, each shippable)

1. **UI modularization** — pure refactor; verified by import/launch smoke test + the
   existing render harness (no visual change) + new `ImagesValidator` unit tests.
2. **Database integration** — depends on `core/paths.py`; verified by repo unit tests
   (get/set/migrate incl. the new-id-exists replace case) and a manual prefill/save/
   migrate walkthrough.
3. **Packaging + updater** — scaffolding + CI; authored and static-checked on Windows,
   really verified on the macOS runner / a Mac (build succeeds, Sparkle shows the
   three-button dialog against a test appcast, pkg postinstall lands browsers).

## Verification

- **Subsystems 1–2 (local, Windows):** `pytest` for `ImagesValidator` and
  `PropertyImagesRepo`; offscreen import + short-lived launch of `autozoopla` to confirm
  the modular shell wires up and pages register.
- **Subsystem 3 (macOS/CI only):** the GitHub Actions run builds the `.app`, produces
  DMG + PKG, signs + generates the appcast; Sparkle update flow and pkg browser install
  confirmed on a Mac. Explicitly out of reach from the Windows dev box.

## Risks

- **Playwright in a bundle** is the highest-risk area: PyInstaller must collect the
  Playwright Python package while the browsers live outside the bundle at a pinned
  `PLAYWRIGHT_BROWSERS_PATH`. Mitigated by the machine-wide path + first-launch safety net.
- **Sparkle ↔ Python bridge:** vendoring `Sparkle.framework` + pyobjc load must happen
  inside a properly-signed bundle; unsigned/misconfigured bundles fail silently.
  Mitigated by the no-op stub off-macOS and CI-side verification.
- **Refactor regressions:** extracting RelistPage/banner/prompt could drop a signal or
  attention behaviour. Mitigated by preserving object names/signals and the smoke +
  render checks.
- **pkg postinstall as root** writing to a per-user cache is the classic footgun;
  avoided by the machine-wide `PLAYWRIGHT_BROWSERS_PATH`.
