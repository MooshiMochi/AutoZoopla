#!/bin/bash
# macOS-only. Build the first-install PKG whose postinstall downloads the
# Playwright browsers. Usage: bash packaging/make_pkg.sh [version]
set -euo pipefail

VERSION="${1:-$(python3 -c 'import runpy,os; print(runpy.run_path(os.path.join("src","relister","__version__.py"))["__version__"])')}"
APP="dist/AutoZoopla.app"
OUT="dist/AutoZoopla-${VERSION}.pkg"
IDENTIFIER="co.uk.rsestateagents.autozoopla"

if [[ ! -d "$APP" ]]; then
    echo "error: $APP not found (run pyinstaller packaging/AutoZoopla.spec first)" >&2
    exit 1
fi

# pkgbuild requires the scripts dir to contain an executable 'postinstall'.
chmod +x packaging/scripts/postinstall

ROOT="$(mktemp -d)"
mkdir -p "$ROOT/Applications"
cp -R "$APP" "$ROOT/Applications/"

pkgbuild \
    --root "$ROOT" \
    --scripts packaging/scripts \
    --identifier "$IDENTIFIER" \
    --version "$VERSION" \
    --install-location / \
    "$OUT"

rm -rf "$ROOT"
echo "Created $OUT"
