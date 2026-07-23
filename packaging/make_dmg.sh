#!/bin/bash
# macOS-only. Package dist/AutoZoopla.app into a compressed DMG (the Sparkle
# update artifact). Usage: bash packaging/make_dmg.sh [version]
set -euo pipefail

VERSION="${1:-$(python3 -c 'import runpy,os; print(runpy.run_path(os.path.join("src","relister","__version__.py"))["__version__"])')}"
APP="dist/AutoZoopla.app"
OUT="dist/AutoZoopla-${VERSION}.dmg"

if [[ ! -d "$APP" ]]; then
    echo "error: $APP not found (run pyinstaller packaging/AutoZoopla.spec first)" >&2
    exit 1
fi

STAGING="$(mktemp -d)"
cp -R "$APP" "$STAGING/"
ln -s /Applications "$STAGING/Applications"

rm -f "$OUT"
hdiutil create \
    -volname "AutoZoopla" \
    -srcfolder "$STAGING" \
    -ov -format UDZO \
    "$OUT"

rm -rf "$STAGING"
echo "Created $OUT"
