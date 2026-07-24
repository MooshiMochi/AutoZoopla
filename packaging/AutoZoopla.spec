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

# PySide6 bundles its own OpenSSL (libssl/libcrypto) for Qt networking, which
# this app never uses. Those libraries collide with cryptography's newer OpenSSL
# (its _rust extension links against libssl at load time), producing a
# "Symbol not found: _SSL_get0_group_name" crash on launch (seen on x86_64).
# Drop the Qt-provided copies so cryptography's OpenSSL is the one that ships.
a.binaries = [
    _b
    for _b in a.binaries
    if not (
        os.path.basename(_b[0]).startswith(("libssl.", "libcrypto."))
        and "PySide6" in (_b[1] or "")
    )
]

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
