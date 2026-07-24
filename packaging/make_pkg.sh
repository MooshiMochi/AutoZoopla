#!/bin/bash
# macOS-only. Build an installer PKG that drops AutoZoopla.app into /Applications.
# Browsers are NOT installed here: the app downloads Firefox + WebKit into a
# per-user cache on first launch (see gui/app.py _ensure_browsers), which avoids
# the root-owned/machine-wide permission problems of a postinstall script.
# Usage: bash packaging/make_pkg.sh [version]
set -euo pipefail

VERSION="${1:-$(python3 -c 'import runpy,os; print(runpy.run_path(os.path.join("src","relister","__version__.py"))["__version__"])')}"
APP="dist/AutoZoopla.app"
OUT="dist/AutoZoopla-${VERSION}.pkg"
IDENTIFIER="co.uk.rsestateagents.autozoopla"

if [[ ! -d "$APP" ]]; then
    echo "error: $APP not found (run pyinstaller packaging/AutoZoopla.spec first)" >&2
    exit 1
fi

ROOT="$(mktemp -d)"
mkdir -p "$ROOT/Applications"
cp -R "$APP" "$ROOT/Applications/"

pkgbuild \
    --root "$ROOT" \
    --identifier "$IDENTIFIER" \
    --version "$VERSION" \
    --install-location / \
    "$OUT"

rm -rf "$ROOT"
echo "Created $OUT"
