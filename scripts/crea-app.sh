#!/bin/zsh
# Assembla build/Blurry.app: l'interfaccia SwiftUI (release, arm64) con dentro
# il motore Python congelato da PyInstaller, firmata ad-hoc.
#
#   scripts/crea-app.sh            app completa (ricostruisce anche il motore)
#   SKIP_ENGINE=1 scripts/crea-app.sh   riusa il motore già in build/engine-dist
#
# Contenuto:
#   Contents/MacOS/Blurry                l'app
#   Contents/Resources/Blurry.icns       l'icona (scripts/icona.sh)
#   Contents/Resources/engine/blurry     il motore, con _internal/ accanto
set -euo pipefail

ROOT=${0:A:h:h}
cd "$ROOT"
APP="$ROOT/build/Blurry.app"
VERSION=$(uv version --short)

# 1. Il motore, in un ambiente senza l'extra "gui": Qt non deve finire qui.
if [[ -z "${SKIP_ENGINE:-}" || ! -x build/engine-dist/engine/blurry ]]; then
  echo "[app] motore (PyInstaller)…"
  UV_PROJECT_ENVIRONMENT=build/engine-venv uv sync --frozen --no-dev --group packaging -q
  if build/engine-venv/bin/python -c "import PySide6" 2>/dev/null; then
    echo "PySide6 nell'ambiente del motore: non deve esserci" >&2
    exit 1
  fi
  build/engine-venv/bin/pyinstaller packaging/blurry-engine.spec --noconfirm --log-level WARN \
    --distpath build/engine-dist --workpath build/engine-work
fi

# 2. L'interfaccia.
echo "[app] interfaccia (swift, release)…"
swift build --package-path macos -c release --arch arm64 -q
BIN="$(swift build --package-path macos -c release --arch arm64 --show-bin-path)/Blurry"

# 3. Il bundle.
echo "[app] assemblo $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/Blurry"
cp macos/Info.plist "$APP/Contents/Info.plist"
plutil -replace CFBundleShortVersionString -string "$VERSION" "$APP/Contents/Info.plist"
cp macos/Blurry.icns "$APP/Contents/Resources/Blurry.icns"
ditto build/engine-dist/engine "$APP/Contents/Resources/engine"

# 4. Firma ad-hoc (nessuna notarizzazione, come Globy) e verifica.
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict "$APP"

# 5. Prova del motore dentro l'app: versione e una foto, senza rete.
ENGINE="$APP/Contents/Resources/engine/blurry"
test "$("$ENGINE" --version)" = "blurry $VERSION"
OUT=$(mktemp -d -t blurry-prova)
trap 'rm -rf "$OUT"' EXIT
"$ENGINE" tests/fixtures/public/dental_squadron.jpg -o "$OUT" --strict >/dev/null 2>&1
test -s "$OUT/dental_squadron.blurry.jpg"

echo "[app] pronta: $APP (versione $VERSION, $(du -sh "$APP" | cut -f1))"
