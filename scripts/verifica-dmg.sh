#!/bin/zsh
# Verifica che un DMG di Blurry contenga l'app, il layout del Finder e un motore
# che parte. Come CANALI/GLOBY/scripts/verifica-dmg.sh, più la prova del motore.
#
#   scripts/verifica-dmg.sh <Blurry.dmg> [versione attesa]
set -euo pipefail

if [[ "$#" -lt 1 || "$#" -gt 2 ]]; then
  echo "Uso: $0 <Blurry.dmg> [versione attesa]" >&2
  exit 2
fi

ARCHIVE=$1
EXPECTED_VERSION=${2:-}
if [[ ! -f "$ARCHIVE" ]]; then
  echo "Errore: DMG non trovato: $ARCHIVE" >&2
  exit 1
fi

MOUNT=$(mktemp -d "${TMPDIR:-/tmp}/blurry-dmg-verifica.XXXXXX")
DEVICE=""

cleanup() {
  if [[ -n "$DEVICE" ]]; then
    hdiutil detach "$DEVICE" -quiet >/dev/null 2>&1 || true
  fi
  [[ -d "$MOUNT" ]] && rmdir "$MOUNT" >/dev/null 2>&1 || true
}
trap cleanup EXIT

ATTACH_OUTPUT=$(hdiutil attach "$ARCHIVE" -readonly -noverify -noautoopen -mountpoint "$MOUNT")
DEVICE=$(printf '%s\n' "$ATTACH_OUTPUT" | awk '/Apple_HFS/ {print $1}')
if [[ -z "$DEVICE" ]]; then
  echo "Errore: impossibile individuare il volume HFS nel DMG." >&2
  exit 1
fi

if [[ ! -d "$MOUNT/Blurry.app" || ! -L "$MOUNT/Applicazioni" ]]; then
  echo "Errore: nel DMG mancano Blurry.app o il collegamento Applicazioni." >&2
  exit 1
fi

for REQUIRED in \
  "$MOUNT/Blurry.app/Contents/Info.plist" \
  "$MOUNT/Blurry.app/Contents/Resources/Blurry.icns" \
  "$MOUNT/Blurry.app/Contents/Resources/engine/blurry" \
  "$MOUNT/Installa e disinstalla Blurry.txt" \
  "$MOUNT/.background/sfondo.tiff" \
  "$MOUNT/.DS_Store"
do
  if [[ ! -s "$REQUIRED" ]]; then
    echo "Errore: nel DMG manca un elemento richiesto: $REQUIRED" >&2
    exit 1
  fi
done

LAYOUT_RECORDS=$(strings "$MOUNT/.DS_Store")
for RECORD in bwsp icvp Iloc sfondo.tiff; do
  if [[ "$LAYOUT_RECORDS" != *"$RECORD"* ]]; then
    echo "Errore: il .DS_Store non contiene il record di layout '$RECORD'." >&2
    exit 1
  fi
done

codesign --verify --deep --strict "$MOUNT/Blurry.app"

ACTUAL_VERSION=$(/usr/libexec/PlistBuddy -c "Print CFBundleShortVersionString" \
  "$MOUNT/Blurry.app/Contents/Info.plist")
if [[ -n "$EXPECTED_VERSION" && "$ACTUAL_VERSION" != "$EXPECTED_VERSION" ]]; then
  echo "Errore: il DMG contiene Blurry $ACTUAL_VERSION, attesa $EXPECTED_VERSION." >&2
  exit 1
fi

# Il motore dentro l'app parte e dichiara la stessa versione.
ENGINE_VERSION=$("$MOUNT/Blurry.app/Contents/Resources/engine/blurry" --version)
if [[ "$ENGINE_VERSION" != "blurry $ACTUAL_VERSION" ]]; then
  echo "Errore: il motore risponde «$ENGINE_VERSION», atteso «blurry $ACTUAL_VERSION»." >&2
  exit 1
fi

hdiutil detach "$DEVICE" -quiet
DEVICE=""
rmdir "$MOUNT"
echo "DMG verificato: Blurry $ACTUAL_VERSION, layout del Finder presente, motore funzionante."
