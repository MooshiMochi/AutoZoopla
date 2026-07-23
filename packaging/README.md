# Packaging & release (macOS)

AutoZoopla ships as a macOS `.app` built with PyInstaller, distributed two ways:

- **First install → `.pkg`.** Its `postinstall` downloads the Playwright browsers
  (Firefox preferred, WebKit fallback) into a machine-wide
  `/Library/Application Support/AutoZoopla/ms-playwright`, which the app reads via
  `PLAYWRIGHT_BROWSERS_PATH` (pinned in `gui/app.py` when frozen).
- **Updates → `.dmg` via Sparkle.** The app checks the appcast on launch and offers
  **Install / Skip This Version / Remind Me Later**. Updates ship the app only; the
  browsers already on disk persist.

Everything below runs on **macOS** (or the GitHub Actions `macos-latest` runner). The
project is developed on Windows, so these steps are authored but verified only on macOS.

## One-time setup

### 1. Sparkle EdDSA keys (no local Mac needed)

You do **not** vendor Sparkle's tools or create a `tools/` directory — the workflows
download Sparkle automatically. To create your signing keypair, run the bootstrap
workflow once:

1. GitHub → **Actions** → **Bootstrap Sparkle keys** → **Run workflow**.
2. Open the finished run's **Summary**: copy the printed **public key** into
   `packaging/Info.plist` under `SUPublicEDKey`.
3. Download the run's **`sparkle-private-key`** artifact, paste its contents into a
   repository secret named **`SPARKLE_PRIVATE_KEY`**, then delete the artifact.

That keypair is permanent — generate it once and reuse it for every release. (If you do
have a Mac, the equivalent is downloading a Sparkle release and running
`bin/generate_keys` locally; the private key lands in your login Keychain and the public
key is printed.)

### 2. Appcast URL

Set `SUFeedURL` in `packaging/Info.plist` to the release-hosted appcast, e.g.
`https://github.com/OWNER/REPO/releases/latest/download/appcast.xml`.

### 3. Apple Developer ID (for Gatekeeper)

Add these secrets so the CI codesign + notarize steps activate (they are skipped when
unset):

| Secret | Purpose |
| --- | --- |
| `APPLE_DEVELOPER_ID` | `Developer ID Application: …` identity for `codesign` |
| `APPLE_ID` | Apple account email for notarization |
| `APPLE_TEAM_ID` | Apple Developer team id |
| `APPLE_APP_PASSWORD` | app-specific password for `notarytool` |

## Local build (on a Mac)

```bash
pip install ".[build,macos]"
pyinstaller packaging/AutoZoopla.spec         # -> dist/AutoZoopla.app
bash packaging/make_dmg.sh                     # -> dist/AutoZoopla-<v>.dmg
bash packaging/make_pkg.sh                     # -> dist/AutoZoopla-<v>.pkg
```

## Cutting a release

1. Bump the version in `src/relister/__version__.py` (the only place — `pyproject.toml`
   and `Info.plist` pick it up automatically).
2. Update `SUPublicEDKey` / `SUFeedURL` in `Info.plist` if not already set.
3. Tag and push: `git tag v0.1.0 && git push --tags`.
4. `.github/workflows/release.yml` builds, (optionally) signs + notarizes, generates the
   Sparkle-signed `appcast.xml`, and attaches `.dmg` + `.pkg` + `appcast.xml` to the
   GitHub Release.

## Notes

- The version lives in `src/relister/__version__.py` and is the single source of truth:
  `pyproject.toml` reads it dynamically (`[tool.setuptools.dynamic]`) and the PyInstaller
  spec injects it into `Info.plist` at build time. Bump it in one place.
- The release workflow downloads Sparkle's binary tools during the run (pinned
  `SPARKLE_VERSION`); nothing Sparkle-related is committed to the repo.
- The `.pkg` postinstall path is duplicated as `_MACOS_BROWSER_CACHE` in
  `src/relister/gui/app.py` — keep the two in sync.
- Hardened-runtime entitlements (`packaging/entitlements.plist`) allow PySide6's JIT and
  Sparkle/pyobjc library loading in a signed bundle.
