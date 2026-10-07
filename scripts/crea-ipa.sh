#!/bin/zsh
# Crea build/Blurry-<versione>.ipa: l'app iOS (ios/Blurry.xcodeproj) in
# release, NON firmata. AltStore o SideStore la firmano con l'Apple ID di chi
# la installa (PIANO_BLURRY, sezione 2, riga «iOS»): niente account a pagamento.
#
#   scripts/crea-ipa.sh
#
# Prima di impacchettare controlla l'app vera:
#   - R1: l'eseguibile non è collegato a nessun framework di rete;
#   - R5: il modello nel pacchetto ha l'hash scritto in Model.swift;
#   - nessuna firma né profilo di provisioning dentro l'IPA.
set -euo pipefail

ROOT=${0:A:h:h}
cd "$ROOT"
VERSION=$(uv version --short)
OUT="$ROOT/build/Blurry-$VERSION.ipa"
WORK=$(mktemp -d -t blurry-ipa)
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$ROOT/build"

echo "[ipa] archivio (xcodebuild, release, senza firma)…"
xcodebuild -project ios/Blurry.xcodeproj -scheme Blurry -configuration Release \
  -destination 'generic/platform=iOS' -archivePath "$WORK/Blurry.xcarchive" \
  -derivedDataPath "$WORK/dd" -quiet archive \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY="" \
  MARKETING_VERSION="$VERSION"
APP="$WORK/Blurry.xcarchive/Products/Applications/Blurry.app"
test -x "$APP/Blurry"

echo "[ipa] R1: framework collegati"
LINKED=$(otool -L "$APP/Blurry")
if print -r -- "$LINKED" | grep -Eq 'Network\.framework|CFNetwork\.framework|libnetwork'; then
  print -r -- "$LINKED" >&2
  echo "[ipa] l'app è collegata a un framework di rete (R1)" >&2
  exit 1
fi

echo "[ipa] R5: hash del modello"
MODEL=$(find "$APP" -type d -name YuNet.mlmodelc | head -1)
PINNED=$(sed -nE 's/.*static let sha256 = "([0-9a-f]{64})".*/\1/p' ios/BlurryKit/Sources/BlurryKit/Model.swift)
FOUND=$(uv run --frozen python scripts/coreml/model_hash.py "$MODEL")
if [[ -z "$MODEL" || "$FOUND" != "$PINNED" ]]; then
  echo "[ipa] il modello nel pacchetto non ha l'hash atteso (R5)" >&2
  exit 1
fi

if [[ -e "$APP/_CodeSignature" || -e "$APP/embedded.mobileprovision" ]]; then
  echo "[ipa] l'app contiene una firma o un profilo: deve uscire non firmata" >&2
  exit 1
fi

mkdir "$WORK/Payload"
ditto "$APP" "$WORK/Payload/Blurry.app"
rm -f "$OUT"
(cd "$WORK" && zip -qry -X "$OUT" Payload)
echo "[ipa] scritto $OUT ($(du -h "$OUT" | cut -f1))"
