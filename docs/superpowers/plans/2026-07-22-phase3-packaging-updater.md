# Phase 3 — macOS Packaging + Sparkle Updater Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Steps use `- [ ]`.

**Goal:** Make AutoZoopla buildable into a signed macOS `.app` (PyInstaller) distributed as a first-install `.pkg` (whose postinstall fetches Firefox+WebKit) with Sparkle-based in-app updates (Install / Skip / Remind Me Later), built on a GitHub Actions macOS runner.

**Architecture:** A cross-platform `gui/updater.py` loads Sparkle via pyobjc only on macOS (no-op elsewhere, so Windows dev is unaffected). `packaging/` holds the PyInstaller spec, Info.plist, entitlements, and DMG/PKG scripts. CI builds + signs on `macos-latest` and publishes DMG + PKG + `appcast.xml`.

**Constraint / honesty:** This phase is authored + static-checked on Windows. The `.app` build, Sparkle bridge, pkg postinstall, and CI are only truly verified on macOS/CI. Steps that can only run on macOS are marked **(macOS-only)**.

**Tech Stack:** PyInstaller, pyobjc (macOS), Sparkle 2, GitHub Actions.

---

## File structure (Phase 3)

```
src/relister/
  __version__.py             # NEW  __version__ (source of truth mirror)
  gui/updater.py             # NEW  SparkleUpdater (pyobjc) + no-op stub
  gui/app.py                 # MODIFY  start updater; add Check-for-Updates hook
packaging/
  AutoZoopla.spec            # NEW  PyInstaller spec
  Info.plist                 # NEW  bundle + Sparkle keys
  entitlements.plist         # NEW  hardened runtime
  make_dmg.sh                # NEW  app -> dmg (Sparkle update artifact)
  make_pkg.sh                # NEW  app -> pkg (first-install; browsers)
  scripts/postinstall        # NEW  playwright install firefox webkit
  README.md                  # NEW  key-gen, signing, notarization docs
.github/workflows/release.yml  # NEW  macos build+sign+appcast+release
pyproject.toml               # MODIFY  version + optional deps (macos, build)
tests/test_updater_stub.py   # NEW  updater is a safe no-op off macOS
tests/test_version.py        # NEW  __version__ importable + matches metadata
```

---

### Task 1: Version source of truth

- [ ] Create `src/relister/__version__.py`:
```python
__version__ = "0.1.0"
```
- [ ] `pyproject.toml`: keep `version = "0.1.0"` (mirror manually or via note). Add optional deps:
```toml
[project.optional-dependencies]
macos = ["pyobjc-core>=10", "pyobjc-framework-Cocoa>=10"]
build = ["pyinstaller>=6"]
```
- [ ] Test `tests/test_version.py`: `from relister.__version__ import __version__; assert __version__` and it equals `importlib.metadata.version("property-relister")` when installed (skip the metadata equality if not installed).
- [ ] Commit `chore: add __version__ and packaging optional deps`.

---

### Task 2: Cross-platform updater

`gui/updater.py` must import cleanly on Windows and be a no-op there.

- [ ] Implement:
```python
# src/relister/gui/updater.py
from __future__ import annotations
import logging, sys
logger = logging.getLogger(__name__)

class SparkleUpdater:
    """Wraps Sparkle's SPUStandardUpdaterController on macOS; no-op elsewhere."""
    def __init__(self) -> None:
        self._controller = None
        self._available = sys.platform == "darwin"

    def start(self, *, check_on_launch: bool = True) -> None:
        if not self._available:
            logger.debug("Updater unavailable on %s; skipping.", sys.platform)
            return
        try:
            import objc  # noqa: F401
            from Foundation import NSBundle  # noqa: F401
            sparkle = self._load_sparkle()
            if sparkle is None:
                return
            SPUStandardUpdaterController = sparkle
            # startingUpdater=True begins scheduled checks per Info.plist keys.
            self._controller = SPUStandardUpdaterController.alloc().initWithStartingUpdater_updaterDelegate_userDriverDelegate_(
                check_on_launch, None, None
            )
        except Exception:  # pragma: no cover - macOS only
            logger.exception("Failed to initialise Sparkle updater")

    def check_for_updates(self) -> None:
        if self._controller is not None:  # pragma: no cover - macOS only
            self._controller.checkForUpdates_(None)

    @staticmethod
    def _load_sparkle():  # pragma: no cover - macOS only
        import objc
        from Foundation import NSBundle
        bundle = NSBundle.mainBundle()
        framework = bundle.privateFrameworksPath() + "/Sparkle.framework"
        loaded = objc.loadBundle("Sparkle", globals(), bundle_path=framework)
        return globals().get("SPUStandardUpdaterController")
```
- [ ] Test `tests/test_updater_stub.py` (runs on Windows): constructing + `start()` + `check_for_updates()` do nothing and don't raise; `_available is False` off macOS.
- [ ] Commit `feat(gui): add cross-platform Sparkle updater (no-op off macOS)`.

---

### Task 3: Wire updater into the app

- [ ] `gui/app.py`: after `window.show()`, create `SparkleUpdater()`, call `.start()`, keep a reference on the window (`window._updater`) so it isn't GC'd. Guard with try/except.
- [ ] (Optional, macOS) A "Check for Updates…" entry — deferred to a menu later; not required for the updater to function (Sparkle auto-checks per Info.plist).
- [ ] Smoke on Windows: `autozoopla` import + launch still fine (updater no-op).
- [ ] Commit `feat(gui): start updater on launch`.

---

### Task 4: PyInstaller spec + Info.plist + entitlements

- [ ] `packaging/AutoZoopla.spec`: a onedir `.app` (`BUNDLE`), name `AutoZoopla.app`, entry `src/relister/gui/app.py:main`, `collect_all('PySide6')`, `collect_submodules('playwright')`, `datas` for `relister` package, `info_plist` referencing the file, `bundle_identifier="co.uk.rsestates.autozoopla"`. **Excludes** the Playwright browser binaries (installed separately).
- [ ] `packaging/Info.plist`: `CFBundleIdentifier`, `CFBundleShortVersionString` (0.1.0), `CFBundleName`, and Sparkle keys:
  - `SUFeedURL` = the release-hosted appcast URL (placeholder `https://…/appcast.xml`)
  - `SUPublicEDKey` = placeholder (filled from generated key)
  - `SUEnableAutomaticChecks` = `true`
  - `LSMinimumSystemVersion` = `12.0`
- [ ] `packaging/entitlements.plist`: hardened-runtime entitlements (`com.apple.security.cs.allow-jit`, `…allow-unsigned-executable-memory`, `…disable-library-validation` — needed for PySide6/Sparkle in a signed bundle).
- [ ] Static check: `python -c "import ast; ast.parse(open('packaging/AutoZoopla.spec').read())"` parses.
- [ ] Commit `build(macos): PyInstaller spec, Info.plist, entitlements`.

---

### Task 5: Browser install (pkg postinstall) + set cache path at runtime

- [ ] `packaging/scripts/postinstall` (bash): set `PLAYWRIGHT_BROWSERS_PATH=/Library/Application Support/AutoZoopla/ms-playwright`, `mkdir -p`, run the app's bundled Python (or system) `playwright install firefox webkit` into it, `chmod -R a+rX`. Documented that it runs as root at install.
- [ ] `gui/app.py` (or a `core/runtime.py`): before Playwright is ever imported/launched, set `os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(core.paths.browser_cache_dir()))`. On macOS default this to the machine-wide dir if it exists, else the per-user cache. (Session already reads the launch via `_launch_browser`.)
- [ ] First-launch safety net: a helper `ensure_browsers()` that checks whether firefox/webkit executables resolve; if not, logs guidance (full GUI download-prompt deferred). Unit-test that it returns a bool without raising.
- [ ] Commit `build(macos): pkg postinstall installs Firefox+WebKit; pin browsers path`.

---

### Task 6: DMG + PKG build scripts

- [ ] `packaging/make_dmg.sh` **(macOS-only)**: `hdiutil create` a compressed DMG from `dist/AutoZoopla.app` → `dist/AutoZoopla-<version>.dmg`.
- [ ] `packaging/make_pkg.sh` **(macOS-only)**: `pkgbuild --root dist/AutoZoopla.app --scripts packaging/scripts --identifier … --version <v> --install-location /Applications/AutoZoopla.app dist/AutoZoopla-<version>.pkg`.
- [ ] `shellcheck`/`bash -n` syntax check both scripts.
- [ ] Commit `build(macos): DMG and PKG build scripts`.

---

### Task 7: GitHub Actions release workflow

- [ ] `.github/workflows/release.yml` on `push: tags: ['v*']`, `runs-on: macos-latest`:
  1. checkout; `actions/setup-python@v5` (3.11)
  2. `pip install .[build,macos]`; `playwright install firefox webkit` (for local build test only)
  3. `pyinstaller packaging/AutoZoopla.spec`
  4. **(codesign)** app with `secrets.APPLE_DEVELOPER_ID` (guarded `if` on secret presence)
  5. `bash packaging/make_dmg.sh` and `bash packaging/make_pkg.sh`
  6. EdDSA-sign the DMG: `Sparkle/bin/sign_update dist/AutoZoopla-*.dmg` using `secrets.SPARKLE_PRIVATE_KEY`
  7. `generate_appcast dist/` → `appcast.xml`
  8. **(notarize)** `xcrun notarytool submit` guarded on `secrets.APPLE_*`
  9. `softprops/action-gh-release` uploads `*.dmg`, `*.pkg`, `appcast.xml`
- [ ] `yamllint`/`python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release.yml'))"` parses.
- [ ] Commit `ci(macos): release workflow (build, sign, appcast, publish)`.

---

### Task 8: packaging/README.md (operator docs)

- [ ] Document: generate Sparkle EdDSA keys (`generate_keys`), where the public key goes (`SUPublicEDKey` in Info.plist), which secrets to set (`SPARKLE_PRIVATE_KEY`, `APPLE_DEVELOPER_ID`, `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD`), the DMG-vs-PKG distribution model, and the machine-wide `PLAYWRIGHT_BROWSERS_PATH`.
- [ ] Commit `docs(packaging): operator guide for signing, keys, notarization`.

---

## Self-review
- Updater imports + no-ops on Windows (unit-tested); real Sparkle path guarded and macOS-only.
- Version single source (`__version__.py`) referenced by Info.plist build.
- Browsers installed at pkg-install into a machine-wide path the app also reads; first-launch net present.
- All shell/yaml/spec files syntax-checked even though full build is macOS/CI-only.
