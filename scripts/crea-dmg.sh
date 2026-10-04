#!/bin/zsh
# Crea build/Blurry-<versione>.dmg e la copia stabile build/Blurry.dmg (nome usato
# dalla Release GitHub e dal README). Stesso impianto del DMG di Globy
# (CANALI/GLOBY/scripts/crea-dmg.sh): finestra con sfondo e freccia, Blurry.app,
# collegamento ad Applicazioni, istruzioni. Firma ad-hoc, nessuna notarizzazione.
# La disposizione della finestra la scrive il Finder: la prima volta macOS può
# chiedere il permesso di controllarlo.
#
#   scripts/crea-dmg.sh               ricostruisce anche l'app (scripts/crea-app.sh)
#   SKIP_APP=1 scripts/crea-dmg.sh    usa build/Blurry.app così com'è
set -euo pipefail

ROOT=${0:A:h:h}
cd "$ROOT"

if [[ -z "${SKIP_APP:-}" || ! -d build/Blurry.app ]]; then
  scripts/crea-app.sh
fi

APP=build/Blurry.app
VERSION=$(/usr/libexec/PlistBuddy -c "Print CFBundleShortVersionString" "$APP/Contents/Info.plist")
WORK=build/dmg
STAGE="$WORK/Blurry"
RW="$WORK/Blurry-rw.dmg"
OUT="build/Blurry-$VERSION.dmg"
STABLE="build/Blurry.dmg"
VOLUME="Blurry"
GUIDE="Installa e disinstalla Blurry.txt"

rm -rf "$WORK" "$OUT" "$STABLE"
mkdir -p "$STAGE/.background"
ditto "$APP" "$STAGE/Blurry.app"
ln -s /Applications "$STAGE/Applicazioni"
cp "scripts/dmg/$GUIDE" "$STAGE/"
swift scripts/dmg/sfondo.swift "$WORK"
tiffutil -cathidpicheck "$WORK/sfondo.png" "$WORK/sfondo@2x.png" -out "$STAGE/.background/sfondo.tiff" >/dev/null

# Un volume con lo stesso nome già montato confonderebbe il Finder.
if [[ -d "/Volumes/$VOLUME" ]]; then hdiutil detach "/Volumes/$VOLUME" -quiet || true; fi

hdiutil create -volname "$VOLUME" -srcfolder "$STAGE" -fs HFS+ -format UDRW -ov "$RW" >/dev/null
DEVICE=$(hdiutil attach "$RW" -readwrite -noverify -noautoopen | awk '/Apple_HFS/ {print $1}')

cleanup_mount() {
  if [[ -n "${DEVICE:-}" ]]; then
    hdiutil detach "$DEVICE" -quiet >/dev/null 2>&1 || true
  fi
}
trap cleanup_mount EXIT

osascript <<APPLESCRIPT
tell application "Finder"
    tell disk "$VOLUME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 120, 860, 628}
        set viewOptions to the icon view options of container window
        set arrangement of viewOptions to not arranged
        set icon size of viewOptions to 112
        set text size of viewOptions to 13
        set background picture of viewOptions to file ".background:sfondo.tiff"
        set position of item "Blurry.app" of container window to {170, 200}
        set position of item "Applicazioni" of container window to {490, 200}
        set position of item "$GUIDE" of container window to {330, 360}
        update without registering applications
        delay 2
        close
        delay 1
    end tell
end tell
APPLESCRIPT

# Sfondo, dimensioni e posizioni vivono nel .DS_Store scritto dal Finder, in modo
# asincrono: si aspetta che la sua dimensione resti ferma per due letture.
LAYOUT="/Volumes/$VOLUME/.DS_Store"
LAYOUT_SIZE=0
STABLE_READS=0
for _ in {1..40}; do
  if [[ -s "$LAYOUT" ]]; then
    CURRENT_SIZE=$(stat -f %z "$LAYOUT")
    if [[ "$CURRENT_SIZE" -eq "$LAYOUT_SIZE" ]]; then
      STABLE_READS=$((STABLE_READS + 1))
    else
      LAYOUT_SIZE=$CURRENT_SIZE
      STABLE_READS=0
    fi
    [[ "$STABLE_READS" -ge 2 ]] && break
  fi
  sleep 0.25
done

if [[ ! -s "$LAYOUT" || "$STABLE_READS" -lt 2 ]]; then
  echo "Errore: il Finder non ha salvato il layout del DMG (.DS_Store)." >&2
  echo "Controlla il permesso di controllare il Finder e riprova." >&2
  exit 1
fi

chmod -Rf go-w "/Volumes/$VOLUME" || true
sync
hdiutil detach "$DEVICE" -quiet
DEVICE=""
CANDIDATE="$WORK/Blurry-final.dmg"
hdiutil convert "$RW" -format UDZO -imagekey zlib-level=9 -o "$CANDIDATE" >/dev/null
scripts/verifica-dmg.sh "$CANDIDATE" "$VERSION"
mv "$CANDIDATE" "$OUT"
rm -rf "$WORK"
cp "$OUT" "$STABLE"
echo "$OUT"
echo "$STABLE"
