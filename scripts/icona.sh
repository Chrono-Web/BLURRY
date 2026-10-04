#!/bin/zsh
# Rigenera macos/Blurry.icns e docs/icona.png (README, Windows e Linux)
# dall'icona disegnata in codice (AppIconArt in macos/Sources/Blurry/AppIcon.swift).
# Si lancia solo quando il disegno cambia; entrambi i file sono committati.
#
#   scripts/icona.sh
#
# Il binario di Debug, con --render-icon, scrive il PNG e si chiude prima di
# avviare qualunque altra cosa (motore compreso).
set -euo pipefail

ROOT=${0:A:h:h}
MACOS="$ROOT/macos"
OUT="$MACOS/Blurry.icns"
WORK=$(mktemp -d -t blurry-icona)
trap 'rm -rf "$WORK"' EXIT

swift build --package-path "$MACOS" -c debug -q
BIN="$(swift build --package-path "$MACOS" -c debug --show-bin-path)/Blurry"

# Limite di 20 secondi: se il render si bloccasse, non resta appeso.
perl -e 'alarm 20; exec @ARGV' "$BIN" --render-icon "$WORK/icon_1024.png"
test -s "$WORK/icon_1024.png"

SET="$WORK/Blurry.iconset"
mkdir "$SET"
for size in 16 32 128 256 512; do
  sips -z $size $size "$WORK/icon_1024.png" --out "$SET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z $double $double "$WORK/icon_1024.png" --out "$SET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$SET" -o "$OUT"
echo "scritto $OUT"
sips -z 256 256 "$WORK/icon_1024.png" --out "$ROOT/docs/icona.png" >/dev/null
echo "scritto $ROOT/docs/icona.png"
