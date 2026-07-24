# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the AutoZoopla macOS app.

Build (on macOS):  pyinstaller packaging/AutoZoopla.spec

Produces dist/AutoZoopla.app. Playwright's *browser binaries* are deliberately
NOT collected here — they are installed separately by the .pkg postinstall into
a machine-wide PLAYWRIGHT_BROWSERS_PATH (see packaging/scripts/postinstall).
"""

import os
import plistlib
import runpy

from PyInstaller.utils.hooks import collect_all, collect_submodules

_here = os.path.dirname(os.path.abspath(SPEC))  # noqa: F821 (SPEC injected by PyInstaller)
_root = os.path.dirname(_here)

# Single source of truth for the version.
_version = runpy.run_path(
    os.path.join(_root, "src", "relister", "__version__.py")
)["__version__"]

_pyside_datas, _pyside_binaries, _pyside_hidden = collect_all("PySide6")
_playwright_hidden = collect_submodules("playwright")

with open(os.path.join(_here, "Info.plist"), "rb") as _plist_file:
    _info_plist = plistlib.load(_plist_file)
_info_plist["CFBundleShortVersionString"] = _version
_info_plist["CFBundleVersion"] = _version

a = Analysis(
    [os.path.join(_root, "src", "relister", "gui", "app.py")],
    pathex=[os.path.join(_root, "src")],
    binaries=_pyside_binaries,
    datas=_pyside_datas,
    hiddenimports=_pyside_hidden + _playwright_hidden + ["relister", "image_manager"],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

# Several packages (PySide6/Qt, Python's stdlib ssl) bundle their own
# libssl/libcrypto. PyInstaller flattens them to one file per name, and an older
# copy was winning over cryptography's newer OpenSSL, whose _rust extension needs
# a 3.2+ symbol -> "Symbol not found: _SSL_get0_group_name" crash on launch.
# Keep ONLY cryptography's OpenSSL (the newest); newer OpenSSL is a superset, so
# Python's ssl resolves against it too.
def _keep_binary(_b):
    _base = os.path.basename(_b[0])
    if _base.startswith(("libssl.", "libcrypto.")):
        return "cryptography" in (_b[1] or "")
    return True


a.binaries = [_b for _b in a.binaries if _keep_binary(_b)]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoZoopla",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    target_arch=None,
    entitlements_file=os.path.join(_here, "entitlements.plist"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AutoZoopla",
)

app = BUNDLE(
    coll,
    name="AutoZoopla.app",
    icon=None,
    bundle_identifier="co.uk.rsestateagents.autozoopla",
    version=_version,
    info_plist=_info_plist,
)
